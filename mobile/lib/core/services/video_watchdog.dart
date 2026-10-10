import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:video_player/video_player.dart';

/// Statut de surveillance émis par le Watchdog
enum VideoHealthStatus {
  healthy,
  buffering,
  stalled,
  recovering,
  error,
}

/// Callbacks d'événements pour le Watchdog
abstract class VideoWatchdogDelegate {
  /// Demande de rechargement complet de la source à la dernière position avec nouveau token
  Future<bool> onReloadRequested({
    required Duration resumePosition,
    required int attempt,
  });

  /// Erreur fatale après épuisement des 3 tentatives
  void onFatalError(String message);

  /// Mise à jour du statut de santé
  void onHealthStatusChanged(VideoHealthStatus status);
}

/// Watchdog haute résilience pour le lecteur vidéo Flutter :
/// 1. Détection des blocages (Stalls) : si la lecture est active mais que la position
///    n'avance plus pendant 8 secondes (ou mise en mémoire tampon anormale > 10s).
/// 2. Récupération automatique avec atérialisation progressive (3 tentatives max).
/// 3. Surveillance réactive des erreurs natives ExoPlayer / AVPlayer (`hasError`).
/// 4. Journalisation détaillée et horodatée de chaque transition d'état.
class VideoWatchdog {
  final String videoId;
  final VideoWatchdogDelegate delegate;
  final int maxRetries;
  final Duration stallThreshold;

  VideoPlayerController? _controller;
  Timer? _timer;

  Duration _lastPosition = Duration.zero;
  int _stallSeconds = 0;
  int _bufferingSeconds = 0;
  int _retryCount = 0;
  bool _isPlaybackDesired = false;
  bool _isRecovering = false;
  VideoHealthStatus _currentStatus = VideoHealthStatus.healthy;

  VideoWatchdog({
    required this.videoId,
    required this.delegate,
    this.maxRetries = 3,
    this.stallThreshold = const Duration(seconds: 8),
  });

  int get retryCount => _retryCount;
  VideoHealthStatus get status => _currentStatus;
  Duration get lastPosition => _lastPosition;

  /// Attache le contrôleur vidéo actif à surveiller
  void attach(VideoPlayerController controller, {bool isPlaybackDesired = true}) {
    _controller = controller;
    _isPlaybackDesired = isPlaybackDesired;
    _lastPosition = controller.value.position;
    _stallSeconds = 0;
    _bufferingSeconds = 0;
    _retryCount = 0;
    _isRecovering = false;
    _updateStatus(VideoHealthStatus.healthy);

    _log('Attachement du contrôleur pour la vidéo $videoId à la position ${_lastPosition.inSeconds}s');

    _startTimer();
  }

  /// Informe le watchdog de l'intention de lecture (lecture ou pause voulue par l'utilisateur)
  void setPlaybackDesired(bool desired) {
    if (_isPlaybackDesired != desired) {
      _isPlaybackDesired = desired;
      _stallSeconds = 0;
      _log('Intention de lecture modifiée: $desired');
    }
  }

  /// Démarre la boucle de surveillance périodique (1 seconde)
  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
  }

  /// Cycle de vérification à chaque seconde
  void _tick() {
    final ctrl = _controller;
    if (ctrl == null || !ctrl.value.isInitialized || _isRecovering) return;

    final value = ctrl.value;
    final currentPos = value.position;
    final duration = value.duration;

    // 1. Détection des erreurs natives
    if (value.hasError) {
      _log('ERREUR NATIVE DÉTECTÉE: ${value.errorDescription}');
      _handleError(value.errorDescription ?? 'Erreur inconnue du lecteur');
      return;
    }

    // Si la vidéo est terminée, rien à surveiller
    if (duration > Duration.zero && currentPos >= duration) {
      _stallSeconds = 0;
      _bufferingSeconds = 0;
      return;
    }

    // 2. Gestion du buffering
    if (value.isBuffering) {
      _bufferingSeconds++;
      _updateStatus(VideoHealthStatus.buffering);

      // Si le buffering dure plus de 10s, c'est probablement un socket gelé
      if (_bufferingSeconds >= 10 && _isPlaybackDesired) {
        _log('Buffering prolongé (${_bufferingSeconds}s) détecté : déclenchement de la relance');
        _triggerRecovery('Buffering réseau interrompu (>10s)');
        return;
      }
    } else {
      _bufferingSeconds = 0;
    }

    // 3. Détection des blocages (Stalls)
    if (_isPlaybackDesired) {
      if (currentPos == _lastPosition) {
        _stallSeconds++;
        if (_stallSeconds >= stallThreshold.inSeconds) {
          _log('BLOCAGE DÉTECTÉ : position figée à ${_lastPosition.inSeconds}s depuis ${_stallSeconds}s');
          _updateStatus(VideoHealthStatus.stalled);
          _triggerRecovery('Position figée depuis ${_stallSeconds}s');
          return;
        }
      } else {
        // La position a avancé correctement !
        if (_stallSeconds > 0) {
          _log('Reprise normale du flux à ${currentPos.inSeconds}s');
        }
        _stallSeconds = 0;
        _bufferingSeconds = 0;
        _lastPosition = currentPos;
        _updateStatus(VideoHealthStatus.healthy);
      }
    } else {
      _stallSeconds = 0;
      _lastPosition = currentPos;
      _updateStatus(VideoHealthStatus.healthy);
    }
  }

  /// Déclenche la procédure de récupération
  Future<void> _triggerRecovery(String reason) async {
    if (_isRecovering) return;
    _isRecovering = true;
    _retryCount++;

    _log('Tentative de récupération ($_retryCount/$maxRetries) suite à : $reason');

    if (_retryCount > maxRetries) {
      _log('Échec définitif après $maxRetries tentatives.');
      _updateStatus(VideoHealthStatus.error);
      delegate.onFatalError('Impossible de poursuivre la lecture. Vérifiez votre connexion.');
      _isRecovering = false;
      return;
    }

    _updateStatus(VideoHealthStatus.recovering);

    // Tentative 1 : simple relance play() si le contrôleur est toujours vivant
    final ctrl = _controller;
    if (_retryCount == 1 && ctrl != null && ctrl.value.isInitialized && !ctrl.value.hasError) {
      try {
        _log('Tentative 1 : Relance locale play()');
        await ctrl.play();
        await Future.delayed(const Duration(milliseconds: 1500));
        if (ctrl.value.position > _lastPosition) {
          _log('Récupération réussie via play() local !');
          _stallSeconds = 0;
          _isRecovering = false;
          _updateStatus(VideoHealthStatus.healthy);
          return;
        }
      } catch (e) {
        _log('Échec du play() local : $e');
      }
    }

    // Tentatives 2 et 3 (ou échec du play() local) : Rechargement complet de la source
    _log('Rechargement complet de la source à la position ${_lastPosition.inSeconds}s avec token frais');
    final success = await delegate.onReloadRequested(
      resumePosition: _lastPosition,
      attempt: _retryCount,
    );

    _isRecovering = false;
    if (success) {
      _log('Rechargement de source réussi !');
      _stallSeconds = 0;
      _bufferingSeconds = 0;
      _updateStatus(VideoHealthStatus.healthy);
    } else {
      _log('Échec de la tentative de rechargement $_retryCount');
      if (_retryCount >= maxRetries) {
        _updateStatus(VideoHealthStatus.error);
        delegate.onFatalError('Connexion interrompue avec le serveur de streaming.');
      }
    }
  }

  /// Gestion directe des erreurs de contrôleur
  void _handleError(String errorMsg) {
    _triggerRecovery('Erreur de lecture ($errorMsg)');
  }

  /// Réinitialise les compteurs de retry (par exemple après une lecture continue réussie)
  void resetRetries() {
    _retryCount = 0;
    _stallSeconds = 0;
    _bufferingSeconds = 0;
    _isRecovering = false;
    _updateStatus(VideoHealthStatus.healthy);
  }

  void _updateStatus(VideoHealthStatus newStatus) {
    if (_currentStatus != newStatus) {
      _currentStatus = newStatus;
      delegate.onHealthStatusChanged(newStatus);
    }
  }

  void _log(String message) {
    final timestamp = DateTime.now().toIso8601String().substring(11, 23);
    debugPrint('[$timestamp] [Watchdog:$videoId] $message');
  }

  /// Libération des ressources du Watchdog
  void dispose() {
    _timer?.cancel();
    _timer = null;
    _controller = null;
    _isRecovering = false;
  }
}
