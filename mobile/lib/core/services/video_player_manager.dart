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
  /// Écouteur d'état (lecture/pause) posé par le gestionnaire pour l'écran allumé
  VoidCallback? ecouteurEtat;

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

  String? _pausedPlayerIdBeforeBackground;
  bool _wasPlayingBeforeBackground = false;

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    debugPrint('[VideoPlayerManager] AppLifecycleState -> $state');
    switch (state) {
      case AppLifecycleState.paused:
      case AppLifecycleState.hidden:
      case AppLifecycleState.detached:
        // L'application n'est réellement plus à l'écran : coupure propre
        if (_activePlayerId != null) {
          final active = _players[_activePlayerId];
          if (active != null && active.controller.value.isInitialized && active.controller.value.isPlaying) {
            _pausedPlayerIdBeforeBackground = _activePlayerId;
            _wasPlayingBeforeBackground = true;
          }
        }
        pauseAll(recordPause: false);
        break;
      case AppLifecycleState.inactive:
        // Sous Android, inactive survient lors d'une notification push, du volet de statut,
        // d'un appui volume ou d'une boîte de dialogue. L'application reste visible.
        // NE PAS couper la lecture ici pour éviter les arrêts inopinés.
        debugPrint('[VideoPlayerManager] Inactive ignoré (maintien lecture en premier plan)');
        break;
      case AppLifecycleState.resumed:
        // Retour au premier plan : reprendre la lecture si elle était active avant
        if (_wasPlayingBeforeBackground && _pausedPlayerIdBeforeBackground != null) {
          final idToResume = _pausedPlayerIdBeforeBackground!;
          _wasPlayingBeforeBackground = false;
          _pausedPlayerIdBeforeBackground = null;
          debugPrint('[VideoPlayerManager] Reprise automatique après retour au premier plan: $idToResume');
          play(idToResume);
        }
        break;
    }
  }

  /// Enregistre un lecteur vidéo dans le gestionnaire central
  void registerPlayer({
    required String id,
    required VideoPlayerController controller,
    VoidCallback? onPauseRequested,
  }) {
    _retirerEcouteur(_players[id]);
    final entree = ManagedPlayerEntry(
      id: id,
      controller: controller,
      onPauseRequested: onPauseRequested,
    );
    // Correctif « le téléphone se verrouille pendant la lecture » : l'écran n'était
    // maintenu allumé que si la lecture passait par ce gestionnaire. Les lectures lancées
    // directement (rejouer, reprise du watchdog, après une annonce...) n'étaient pas vues.
    // On écoute désormais chaque lecteur : écran allumé dès que l'un d'eux joue.
    entree.ecouteurEtat = _updateWakelockState;
    controller.addListener(entree.ecouteurEtat!);
    _players[id] = entree;
    _updateWakelockState();
  }

  void _retirerEcouteur(ManagedPlayerEntry? entree) {
    final ecouteur = entree?.ecouteurEtat;
    if (entree == null || ecouteur == null) return;
    try {
      entree.controller.removeListener(ecouteur);
    } catch (_) {
      // Contrôleur déjà libéré : rien à retirer
    }
    entree.ecouteurEtat = null;
  }

  /// Dé-référence un lecteur vidéo lorsqu'il est libéré (dispose)
  void unregisterPlayer(String id) {
    if (_activePlayerId == id) {
      _activePlayerId = null;
    }
    _retirerEcouteur(_players.remove(id));
    _updateWakelockState();
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
  void pauseAll({bool recordPause = true}) {
    if (recordPause) {
      _wasPlayingBeforeBackground = false;
      _pausedPlayerIdBeforeBackground = null;
    }
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
  bool? _ecranMaintenuAllume;

  /// Vrai si l'écran est actuellement maintenu allumé par le gestionnaire.
  bool get ecranMaintenuAllume => _ecranMaintenuAllume ?? false;

  void _updateWakelockState() {
    final anyPlaying = _players.values.any((p) {
      try {
        return p.controller.value.isInitialized && p.controller.value.isPlaying;
      } catch (_) {
        return false; // contrôleur libéré entre-temps
      }
    });
    // Appelé à chaque mise à jour de position : on n'agit que si l'état change
    if (anyPlaying == _ecranMaintenuAllume) return;
    _ecranMaintenuAllume = anyPlaying;
    debugPrint('[Écran] maintenu allumé : ${anyPlaying ? 'oui' : 'non'}');
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
    for (final entree in _players.values) {
      _retirerEcouteur(entree);
    }
    _players.clear();
    _activePlayerId = null;
    _ecranMaintenuAllume = false;
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
