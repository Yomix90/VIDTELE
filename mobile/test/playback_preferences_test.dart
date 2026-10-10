import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:vidtele_mobile/core/storage/storage_service.dart';
import 'package:vidtele_mobile/core/localization/app_localizations.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Playback Preferences & StorageService Tests', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('Valeurs par défaut du masquage automatique', () async {
      final storage = StorageService();
      final autoHide = await storage.getAutoHideControls();
      final seconds = await storage.getAutoHideSeconds();

      expect(autoHide, true);
      expect(seconds, 3);
    });

    test('Modification et persistance des réglages de masquage', () async {
      final storage = StorageService();

      await storage.setAutoHideControls(false);
      var autoHide = await storage.getAutoHideControls();
      expect(autoHide, false);

      await storage.setAutoHideSeconds(5);
      var seconds = await storage.getAutoHideSeconds();
      expect(seconds, 5);

      await storage.setAutoHideControls(true);
      await storage.setAutoHideSeconds(8);
      autoHide = await storage.getAutoHideControls();
      seconds = await storage.getAutoHideSeconds();

      expect(autoHide, true);
      expect(seconds, 8);
    });

    test('Traductions trilingues FR / EN / AR des préférences de lecture', () {
      final l10nFr = AppLocalizations(const Locale('fr'));
      expect(l10nFr.playbackPreferencesHeader, 'Préférences de Lecture');
      expect(l10nFr.autoHideControlsTitle, 'Masquer automatiquement les boutons');
      expect(l10nFr.autoHideSecondsSummary(3), '3 secondes');

      final l10nEn = AppLocalizations(const Locale('en'));
      expect(l10nEn.playbackPreferencesHeader, 'Playback Preferences');
      expect(l10nEn.autoHideControlsTitle, 'Auto-hide controls');
      expect(l10nEn.autoHideSecondsSummary(5), '5 seconds');

      final l10nAr = AppLocalizations(const Locale('ar'));
      expect(l10nAr.playbackPreferencesHeader, 'إعدادات التشغيل');
      expect(l10nAr.autoHideControlsTitle, 'إخفاء الأزرار تلقائياً');
      expect(l10nAr.autoHideSecondsSummary(8), '8 ثوانٍ');
    });
  });
}
