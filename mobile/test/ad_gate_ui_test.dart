import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vidtele_mobile/core/localization/app_localizations.dart';
import 'package:vidtele_mobile/widgets/ad_gate_locked_overlay.dart';
import 'package:vidtele_mobile/widgets/ad_gate_prompt_sheet.dart';

Widget createLocalizedTestApp(Widget child, {Locale locale = const Locale('fr')}) {
  return MaterialApp(
    locale: locale,
    supportedLocales: const [
      Locale('fr'),
      Locale('ar'),
      Locale('en'),
    ],
    localizationsDelegates: const [
      AppLocalizations.delegate,
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
      GlobalCupertinoLocalizations.delegate,
    ],
    home: Scaffold(body: child),
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('AdGate UI Components Tests', () {
    testWidgets('AdGatePromptSheet affiche correctement les textes FR et réagit aux clics', (tester) async {
      bool watchClicked = false;
      bool laterClicked = false;

      await tester.pumpWidget(
        createLocalizedTestApp(
          AdGatePromptSheet(
            videosToUnlock: 5,
            onWatchAd: () => watchClicked = true,
            onLater: () => laterClicked = true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Vérification des textes FR
      expect(find.text('Débloquer plus de vidéos'), findsOneWidget);
      expect(find.text('Regardez une courte vidéo publicitaire pour débloquer 5 vidéos de plus.'), findsOneWidget);
      expect(find.text('Regarder la pub'), findsOneWidget);
      expect(find.text('Plus tard'), findsOneWidget);

      // Clic sur "Regarder la pub"
      await tester.tap(find.text('Regarder la pub'));
      await tester.pump();
      expect(watchClicked, isTrue);

      // Clic sur "Plus tard"
      await tester.tap(find.text('Plus tard'));
      await tester.pump();
      expect(laterClicked, isTrue);
    });

    testWidgets('AdGatePromptSheet supporte la langue arabe (RTL)', (tester) async {
      await tester.pumpWidget(
        createLocalizedTestApp(
          AdGatePromptSheet(
            videosToUnlock: 4,
            onWatchAd: () {},
            onLater: () {},
          ),
          locale: const Locale('ar'),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('فتح المزيد من مقاطع الفيديو'), findsOneWidget);
      expect(find.text('شاهد إعلاناً قصيراً لفتح 4 مقاطع فيديو جديدة مجاناً.'), findsOneWidget);
      expect(find.text('مشاهدة الإعلان'), findsOneWidget);
      expect(find.text('لاحقاً'), findsOneWidget);
    });

    testWidgets('AdGateLockedOverlay affiche le cadenas, le message de verrouillage et déclenche l\'action', (tester) async {
      bool adClicked = false;
      bool backClicked = false;

      await tester.pumpWidget(
        createLocalizedTestApp(
          AdGateLockedOverlay(
            onWatchAd: () => adClicked = true,
            onBack: () => backClicked = true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.lock_rounded), findsOneWidget);
      expect(find.text('Limite de visionnage atteinte'), findsOneWidget);
      expect(find.text('Vous avez atteint votre quota de vidéos. Regardez une courte pub pour continuer.'), findsOneWidget);
      expect(find.text('Regarder la pub'), findsOneWidget);
      expect(find.text('Annuler'), findsOneWidget);

      await tester.tap(find.text('Regarder la pub'));
      await tester.pump();
      expect(adClicked, isTrue);

      await tester.tap(find.text('Annuler'));
      await tester.pump();
      expect(backClicked, isTrue);
    });
  });
}
