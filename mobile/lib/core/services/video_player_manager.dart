import 'dart:async';
import 'package:audio_session/audio_session.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

/// Callback de commande pour un lecteur enregistré
class ManagedPlayerEntry {
  final String id;
  final VideoPlayerController controller;
  final VoidCallback? onPauseRequested;

  ManagedPlayerEntry({
    required this.id,
    required this.controller,
    this.onPauseRequested,
  });
}

/// Gestionnaire centralisé garantissant :
/// 1. La règle d'or : au maximum UN SEUL flux / audio actif dans toute l'application.
/// 2. La mise en pause automatique lors des interruptions système (appels, notifications).
/// 3. La mise en pause automatique lors du débranchement des écouteurs.
/// 4. La mise en pause immédiate quand l'app passe en arrière-plan (paused, inactive, hidden).
/// 5. L'activation et la désactivation rigoureuse du maintien de l'écran allumé (Wakelock).
class VideoPlayerManager with WidgetsBindingObserver {
  static final VideoPlayerManager _instance = VideoPlayerManager._internal();
  factory VideoPlayerManager() => _instance;

  VideoPlayerManager._internal() {
    _initLifecycleObserver();
    _initAudioSession();
  }

  final Map<String, ManagedPlayerEntry> _players = {};
  String? _activePlayerId;
  AudioSession? _audioSession;
  StreamSubscription? _interruptionSub;
  StreamSubscription? _becomingNoisySub;
  bool _isAudioSessionConfigured = false;

  /// Identifiant du lecteur actuellement en cours de lecture (null si aucun)
  String? get activePlayerId => _activePlayerId;

  /// Initialise l'observation du cycle de vie de l'application
  void _initLifecycleObserver() {
    WidgetsBinding.instance.addObserver(this);
  }

  /// Initialise l'interception des interruptions audio du système Android / iOS
  Future<void> _initAudioSession() async {
    try {
      _audioSession = await AudioSession.instance;
      await _audioSession?.configure(const AudioSessionConfiguration.music());
      _isAudioSessionConfigured = true;

      // Écoute de la perte de focus audio (appel téléphonique entrant, autre appli qui démarre)
      _interruptionSub = _audioSession?.interruptionEventStream.listen((event) {
        if (event.begin) {
          pauseAll();
        }
      });

      // Écoute du débranchement physique ou bluetooth des écouteurs
      _becomingNoisySub = _audioSession?.becomingNoisyEventStream.listen((_) {
        pauseAll();
      });
    } catch (_) {
      // Tolérance environnement de test unitaire
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.paused:
      case AppLifecycleState.inactive:
      case AppLifecycleState.hidden:
      case AppLifecycleState.detached:
        // Coupure absolue du son et de la vidéo dès que l'app n'est plus au premier plan
        pauseAll();
        break;
      case AppLifecycleState.resumed:
        // Ne reprend pas automatiquement pour éviter tout son surprise non désiré
        break;
    }
  }

  /// Enregistre un lecteur vidéo dans le gestionnaire central
  void registerPlayer({
    required String id,
    required VideoPlayerController controller,
    VoidCallback? onPauseRequested,
  }) {
    _players[id] = ManagedPlayerEntry(
      id: id,
      controller: controller,
      onPauseRequested: onPauseRequested,
    );
  }

  /// Dé-référence un lecteur vidéo lorsqu'il est libéré (dispose)
  void unregisterPlayer(String id) {
    if (_activePlayerId == id) {
      _activePlayerId = null;
      _updateWakelockState();
    }
    _players.remove(id);
  }

  /// Démarre ou reprend la lecture d'un contrôleur spécifique.
  /// Met immédiatement en pause TOUS les autres lecteurs de l'application.
  Future<void> play(String id) async {
    final target = _players[id];
    if (target == null) return;

    // 1. Mettre en pause tous les autres lecteurs enregistrés
    _players.forEach((key, entry) {
      if (key != id) {
        if (entry.controller.value.isPlaying) {
          entry.controller.pause();
        }
        entry.onPauseRequested?.call();
      }
    });

    // 2. Activer la session audio
    if (_isAudioSessionConfigured && _audioSession != null) {
      await _audioSession!.setActive(true);
    }

    // 3. Lancer le contrôleur cible
    await target.controller.play();
    _activePlayerId = id;

    // 4. Maintenir l'écran éveillé
    _updateWakelockState();
  }

  /// Met en pause un lecteur spécifique
  Future<void> pause(String id) async {
    final target = _players[id];
    if (target != null) {
      await target.controller.pause();
      target.onPauseRequested?.call();
    }
    if (_activePlayerId == id) {
      _activePlayerId = null;
    }
    _updateWakelockState();
  }

  /// Met en pause TOUS les lecteurs actifs enregistrés
  void pauseAll() {
    _players.forEach((_, entry) {
      if (entry.controller.value.isInitialized && entry.controller.value.isPlaying) {
        entry.controller.pause();
      }
      entry.onPauseRequested?.call();
    });
    _activePlayerId = null;
    _updateWakelockState();
  }

  /// Ajuste l'état du wakelock selon qu'une vidéo est en train de jouer ou non
  void _updateWakelockState() {
    final anyPlaying = _players.values.any(
      (p) => p.controller.value.isInitialized && p.controller.value.isPlaying,
    );

    if (anyPlaying) {
      WakelockPlus.enable().catchError((_) {});
    } else {
      WakelockPlus.disable().catchError((_) {});
    }
  }

  /// Nettoyage général (tests ou fermeture globale)
  void dispose() {
    pauseAll();
    WidgetsBinding.instance.removeObserver(this);
    _interruptionSub?.cancel();
    _becomingNoisySub?.cancel();
    _players.clear();
    _activePlayerId = null;
    WakelockPlus.disable().catchError((_) {});
  }
}

/// Provider Riverpod pour injecter et accéder au VideoPlayerManager
final videoPlayerManagerProvider = Provider<VideoPlayerManager>((ref) {
  final manager = VideoPlayerManager();
  ref.onDispose(() {
    // Garder le singleton vivant ou le nettoyer si nécessaire
  });
  return manager;
});
