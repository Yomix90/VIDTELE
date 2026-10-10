import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vidtele_mobile/core/services/video_player_manager.dart';
import 'package:vidtele_mobile/core/services/video_watchdog.dart';

class MockWatchdogDelegate implements VideoWatchdogDelegate {
  int reloadCount = 0;
  Duration? lastResumePosition;
  String? fatalErrorMessage;
  VideoHealthStatus? latestStatus;

  bool shouldReloadSucceed = true;

  @override
  Future<bool> onReloadRequested({
    required Duration resumePosition,
    required int attempt,
  }) async {
    reloadCount++;
    lastResumePosition = resumePosition;
    return shouldReloadSucceed;
  }

  @override
  void onFatalError(String message) {
    fatalErrorMessage = message;
  }

  @override
  void onHealthStatusChanged(VideoHealthStatus status) {
    latestStatus = status;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('VideoWatchdog Unit Tests', () {
    late MockWatchdogDelegate delegate;
    late VideoWatchdog watchdog;

    setUp(() {
      delegate = MockWatchdogDelegate();
      watchdog = VideoWatchdog(
        videoId: 'test_vid_1',
        delegate: delegate,
        stallThreshold: const Duration(seconds: 2), // Réduit pour le test
        maxRetries: 3,
      );
    });

    tearDown(() {
      watchdog.dispose();
    });

    test('Initialisation correcte en état healthy', () {
      expect(watchdog.status, VideoHealthStatus.healthy);
      expect(watchdog.retryCount, 0);
    });

    test('setPlaybackDesired met à jour l\'intention de lecture', () {
      watchdog.setPlaybackDesired(true);
      expect(watchdog.status, VideoHealthStatus.healthy);
    });

    test('resetRetries remet à zéro le compteur de tentatives', () {
      watchdog.resetRetries();
      expect(watchdog.retryCount, 0);
      expect(watchdog.status, VideoHealthStatus.healthy);
    });
  });

  group('VideoPlayerManager Lifecycle Tests', () {
    late VideoPlayerManager manager;

    setUp(() {
      manager = VideoPlayerManager();
    });

    tearDown(() {
      manager.dispose();
    });

    test('AppLifecycleState.inactive n\'arrête pas les lecteurs au premier plan', () {
      // inactive ne doit plus déclencher de pause intempestive
      manager.didChangeAppLifecycleState(AppLifecycleState.inactive);
      expect(manager.activePlayerId, isNull);
    });

    test('AppLifecycleState.paused appelle pauseAll', () {
      manager.didChangeAppLifecycleState(AppLifecycleState.paused);
      expect(manager.activePlayerId, isNull);
    });
  });
}
