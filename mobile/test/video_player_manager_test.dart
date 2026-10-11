import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:video_player/video_player.dart';
import 'package:vidtele_mobile/core/services/video_player_manager.dart';

/// Contrôleur mock léger pour simuler les opérations de lecture/pause sans canal natif
class FakeVideoPlayerController extends VideoPlayerController {
  bool isPlayingState = false;
  bool wasDisposed = false;

  FakeVideoPlayerController() : super.networkUrl(Uri.parse('https://example.com/test.mp4')) {
    value = const VideoPlayerValue(
      duration: Duration(seconds: 100),
      isInitialized: true,
      isPlaying: false,
    );
  }

  @override
  Future<void> play() async {
    isPlayingState = true;
    value = value.copyWith(isPlaying: true);
  }

  @override
  Future<void> pause() async {
    isPlayingState = false;
    value = value.copyWith(isPlaying: false);
  }

  @override
  Future<void> dispose() async {
    wasDisposed = true;
    super.dispose();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late VideoPlayerManager manager;
  late FakeVideoPlayerController controller1;
  late FakeVideoPlayerController controller2;

  setUp(() {
    manager = VideoPlayerManager();
    manager.pauseAll();
    controller1 = FakeVideoPlayerController();
    controller2 = FakeVideoPlayerController();
  });

  tearDown(() {
    manager.pauseAll();
    manager.unregisterPlayer('player_1');
    manager.unregisterPlayer('player_2');
  });

  group('VideoPlayerManager - Règle du lecteur unique', () {
    test('Lancer un second lecteur met automatiquement en pause le premier', () async {
      bool player1PausedCallback = false;

      manager.registerPlayer(
        id: 'player_1',
        controller: controller1,
        onPauseRequested: () => player1PausedCallback = true,
      );
      manager.registerPlayer(
        id: 'player_2',
        controller: controller2,
      );

      // 1. Démarrage du premier lecteur
      await manager.play('player_1');
      expect(manager.activePlayerId, 'player_1');
      expect(controller1.isPlayingState, isTrue);

      // 2. Démarrage du second lecteur
      await manager.play('player_2');

      // Le lecteur 1 doit être mis en pause immédiatement
      expect(manager.activePlayerId, 'player_2');
      expect(controller1.isPlayingState, isFalse);
      expect(player1PausedCallback, isTrue);
      expect(controller2.isPlayingState, isTrue);
    });

    test('pauseAll() met en pause tous les contrôleurs actifs', () async {
      bool player1PausedCallback = false;

      manager.registerPlayer(
        id: 'player_1',
        controller: controller1,
        onPauseRequested: () => player1PausedCallback = true,
      );

      await manager.play('player_1');
      expect(controller1.isPlayingState, isTrue);

      manager.pauseAll();

      expect(manager.activePlayerId, isNull);
      expect(controller1.isPlayingState, isFalse);
      expect(player1PausedCallback, isTrue);
    });

    test('unregisterPlayer retire le lecteur du gestionnaire', () async {
      manager.registerPlayer(
        id: 'player_1',
        controller: controller1,
      );

      await manager.play('player_1');
      expect(manager.activePlayerId, 'player_1');

      manager.unregisterPlayer('player_1');
      expect(manager.activePlayerId, isNull);
    });
  });

  group('VideoPlayerManager - Cycle de vie de l\'application (Arrière-plan)', () {
    test('AppLifecycleState.paused coupe immédiatement tous les flux', () async {
      manager.registerPlayer(
        id: 'player_1',
        controller: controller1,
      );

      await manager.play('player_1');
      expect(controller1.isPlayingState, isTrue);

      // Simulation du passage en arrière-plan (Bouton Home / changement d'application)
      manager.didChangeAppLifecycleState(AppLifecycleState.paused);

      expect(controller1.isPlayingState, isFalse);
      expect(manager.activePlayerId, isNull);
    });

    test('AppLifecycleState.inactive (notification ou overlay système) maintient la lecture au premier plan', () async {
      manager.registerPlayer(
        id: 'player_1',
        controller: controller1,
      );

      await manager.play('player_1');
      expect(controller1.isPlayingState, isTrue);

      // Simulation d'une notification push ou réglage du volume système
      manager.didChangeAppLifecycleState(AppLifecycleState.inactive);

      // La lecture reste active au premier plan
      expect(controller1.isPlayingState, isTrue);
      expect(manager.activePlayerId, equals('player_1'));
    });

    test('AppLifecycleState.paused puis resumed reprend la lecture automatiquement', () async {
      manager.registerPlayer(
        id: 'player_1',
        controller: controller1,
      );

      await manager.play('player_1');
      expect(controller1.isPlayingState, isTrue);

      // Passage en arrière-plan
      manager.didChangeAppLifecycleState(AppLifecycleState.paused);
      expect(controller1.isPlayingState, isFalse);

      // Retour au premier plan
      manager.didChangeAppLifecycleState(AppLifecycleState.resumed);
      await Future.delayed(Duration.zero);
      expect(controller1.isPlayingState, isTrue);
      expect(manager.activePlayerId, equals('player_1'));
    });

    test('AppLifecycleState.hidden (écran verrouillé) coupe immédiatement le son', () async {
      manager.registerPlayer(
        id: 'player_1',
        controller: controller1,
      );

      await manager.play('player_1');
      expect(controller1.isPlayingState, isTrue);

      // Simulation de la mise en veille ou verrouillage de l'écran
      manager.didChangeAppLifecycleState(AppLifecycleState.hidden);

      expect(controller1.isPlayingState, isFalse);
      expect(manager.activePlayerId, isNull);
    });
  });

  test("écran maintenu allumé même si la lecture est lancée directement (sans le gestionnaire)", () async {
    // Reproduit le bug « le téléphone se verrouille pendant la lecture »
    final manager = VideoPlayerManager();
    final controleur = FakeVideoPlayerController();
    manager.registerPlayer(id: 'direct', controller: controleur);
    expect(manager.ecranMaintenuAllume, isFalse);

    await controleur.play(); // ex. « rejouer » ou reprise du watchdog
    expect(manager.ecranMaintenuAllume, isTrue);

    await controleur.pause();
    expect(manager.ecranMaintenuAllume, isFalse);

    await controleur.play();
    manager.unregisterPlayer('direct'); // lecteur libéré : plus besoin de l'écran allumé
    expect(manager.ecranMaintenuAllume, isFalse);
  });
}
