import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:vidtele_mobile/core/ads/watch_gate_controller.dart';
import 'package:vidtele_mobile/models/user_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('WatchGateController Unit Tests', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('Initialisation par défaut tire un seuil entre 4 et 5', () async {
      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 5);
      await controller.initialize();

      expect(controller.isInitialized, isTrue);
      expect(controller.watchedCount, equals(0));
      expect(controller.isGateLocked, isFalse);
      expect(controller.currentCycleThreshold, inInclusiveRange(4, 5));
      expect(controller.remainingVideos, equals(controller.currentCycleThreshold));
    });

    test('Restauration exacte de l\'état depuis SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({
        WatchGateController.keyWatchCount: 3,
        WatchGateController.keyCycleThreshold: 5,
        WatchGateController.keyGateLocked: false,
        WatchGateController.keyWatchedIds: ['vid_1', 'vid_2', 'vid_3'],
      });

      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 5);
      await controller.initialize();

      expect(controller.watchedCount, equals(3));
      expect(controller.currentCycleThreshold, equals(5));
      expect(controller.isGateLocked, isFalse);
      expect(controller.remainingVideos, equals(2));
      expect(controller.watchedVideoIds, containsAll(['vid_1', 'vid_2', 'vid_3']));
    });

    test('Une vidéo à moins de 70% de visionnage n\'est PAS comptée', () async {
      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 5);
      await controller.initialize();

      // Lecture à 50% (50s sur 100s)
      final locked = controller.recordVideoProgress(
        videoId: 'vid_short',
        position: const Duration(seconds: 50),
        duration: const Duration(seconds: 100),
      );

      expect(locked, isFalse);
      expect(controller.watchedCount, equals(0));
      expect(controller.watchedVideoIds.contains('vid_short'), isFalse);
    });

    test('Une vidéo à 70% ou plus est comptabilisée', () async {
      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 5);
      await controller.initialize();

      // Lecture à 70% (70s sur 100s)
      final locked = controller.recordVideoProgress(
        videoId: 'vid_70',
        position: const Duration(seconds: 70),
        duration: const Duration(seconds: 100),
      );

      expect(locked, isFalse); // Car seuil 4 ou 5 non atteint
      expect(controller.watchedCount, equals(1));
      expect(controller.watchedVideoIds.contains('vid_70'), isTrue);
    });

    test('Une vidéo marquée completed=true est toujours comptabilisée', () async {
      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 5);
      await controller.initialize();

      final locked = controller.recordVideoProgress(
        videoId: 'vid_ended',
        position: const Duration(seconds: 20),
        duration: const Duration(seconds: 100),
        completed: true,
      );

      expect(locked, isFalse);
      expect(controller.watchedCount, equals(1));
      expect(controller.watchedVideoIds.contains('vid_ended'), isTrue);
    });

    test('Une même vidéo n\'est jamais comptabilisée deux fois dans un cycle', () async {
      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 5);
      await controller.initialize();

      // Premier signal à 75%
      controller.recordVideoProgress(
        videoId: 'vid_repeat',
        position: const Duration(seconds: 75),
        duration: const Duration(seconds: 100),
      );
      expect(controller.watchedCount, equals(1));

      // Deuxième signal sur la même vidéo à 90%
      controller.recordVideoProgress(
        videoId: 'vid_repeat',
        position: const Duration(seconds: 90),
        duration: const Duration(seconds: 100),
      );
      // Le compteur DOIT rester à 1
      expect(controller.watchedCount, equals(1));

      // Troisième signal sur la même vidéo avec completed=true
      controller.recordVideoProgress(
        videoId: 'vid_repeat',
        position: const Duration(seconds: 100),
        duration: const Duration(seconds: 100),
        completed: true,
      );
      expect(controller.watchedCount, equals(1));
    });

    test('Le seuil verrouille le quota (isGateLocked = true) au nombre requis de vidéos', () async {
      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 4);
      await controller.initialize();
      expect(controller.currentCycleThreshold, equals(4));

      // 1ère vidéo
      expect(
        controller.recordVideoProgress(
          videoId: 'v1',
          position: const Duration(seconds: 80),
          duration: const Duration(seconds: 100),
        ),
        isFalse,
      );
      expect(controller.watchedCount, equals(1));
      expect(controller.isGateLocked, isFalse);

      // 2ème vidéo
      controller.recordVideoProgress(
        videoId: 'v2',
        position: const Duration(seconds: 80),
        duration: const Duration(seconds: 100),
      );
      expect(controller.watchedCount, equals(2));

      // 3ème vidéo
      controller.recordVideoProgress(
        videoId: 'v3',
        position: const Duration(seconds: 80),
        duration: const Duration(seconds: 100),
      );
      expect(controller.watchedCount, equals(3));
      expect(controller.isGateLocked, isFalse);

      // 4ème vidéo -> ATTEINTE DU SEUIL !
      final locked = controller.recordVideoProgress(
        videoId: 'v4',
        position: const Duration(seconds: 80),
        duration: const Duration(seconds: 100),
      );
      expect(locked, isTrue);
      expect(controller.watchedCount, equals(4));
      expect(controller.isGateLocked, isTrue);
      expect(controller.remainingVideos, equals(0));

      // Tentative suivante alors que verrouillé
      expect(
        controller.recordVideoProgress(
          videoId: 'v5',
          position: const Duration(seconds: 80),
          duration: const Duration(seconds: 100),
        ),
        isTrue,
      );
    });

    test('unlockNewCycle réinitialise le compteur et tire un nouveau seuil', () async {
      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 5);
      await controller.initialize();
      await controller.resetState(forcedThreshold: 4);

      for (int i = 1; i <= 4; i++) {
        controller.recordVideoProgress(
          videoId: 'v_$i',
          position: const Duration(seconds: 70),
          duration: const Duration(seconds: 100),
        );
      }
      expect(controller.isGateLocked, isTrue);

      // Déblocage suite à la récompense
      await controller.unlockNewCycle();

      expect(controller.isGateLocked, isFalse);
      expect(controller.watchedCount, equals(0));
      expect(controller.watchedVideoIds, isEmpty);
      expect(controller.currentCycleThreshold, inInclusiveRange(4, 5));
    });

    test('Exemption totale pour les comptes Admin et sans publicité (adsFree)', () async {
      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 5);
      await controller.initialize();

      final adminUser = UserModel(
        id: 1,
        username: 'admin',
        role: 'admin',
        isActive: true,
        maxConcurrentStreams: 5,
        adsFree: false,
      );

      final adsFreeUser = UserModel(
        id: 2,
        username: 'vip_user',
        role: 'user',
        isActive: true,
        maxConcurrentStreams: 2,
        adsFree: true,
      );

      final normalUser = UserModel(
        id: 3,
        username: 'normal_user',
        role: 'user',
        isActive: true,
        maxConcurrentStreams: 2,
        adsFree: false,
      );

      expect(controller.isUserExempt(adminUser), isTrue);
      expect(controller.isUserExempt(adsFreeUser), isTrue);
      expect(controller.isUserExempt(normalUser), isFalse);

      // L'utilisateur admin regarde une vidéo : elle n'est pas comptée dans le quota de pub
      final resAdmin = controller.recordVideoProgress(
        videoId: 'admin_video',
        position: const Duration(seconds: 90),
        duration: const Duration(seconds: 100),
        user: adminUser,
      );
      expect(resAdmin, isFalse);
      expect(controller.watchedCount, equals(0));

      // L'utilisateur normal regarde une vidéo : elle est comptabilisée
      final resNormal = controller.recordVideoProgress(
        videoId: 'normal_video',
        position: const Duration(seconds: 90),
        duration: const Duration(seconds: 100),
        user: normalUser,
      );
      expect(resNormal, isFalse);
      expect(controller.watchedCount, equals(1));
    });

    test('grantEmergencyBypass permet de débloquer l\'accès en cas de panne réseau', () async {
      final controller = WatchGateController.custom(minVideos: 4, maxVideos: 4);
      await controller.initialize();

      // Verrouiller
      await controller.lockGate();
      expect(controller.isGateLocked, isTrue);

      // Accorder dérogation de 1 vidéo
      await controller.grantEmergencyBypass(extraVideos: 1);
      expect(controller.isGateLocked, isFalse);
      expect(controller.currentCycleThreshold, equals(5));
    });
  });
}
