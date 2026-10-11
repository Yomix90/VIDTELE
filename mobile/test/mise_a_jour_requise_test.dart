import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vidtele_mobile/core/localization/app_localizations.dart';
import 'package:vidtele_mobile/core/version/mise_a_jour_requise.dart';
import 'package:vidtele_mobile/widgets/ecran_mise_a_jour_requise.dart';

void main() {
  test('lecture de la réponse 426 du serveur', () {
    final info = InfoMiseAJourRequise.depuisJson(const {
      'detail': 'Mise à jour requise',
      'code': 'mise_a_jour_requise',
      'min_version': '1.3.0',
      'download_url': '/static/uploads/apk/atlas-play.apk',
    });
    expect(info.versionMinimale, '1.3.0');
    expect(info.urlTelechargement, '/static/uploads/apk/atlas-play.apk');

    final vide = InfoMiseAJourRequise.depuisJson(null);
    expect(vide.urlTelechargement, isNull);
    expect(vide.message, isNotEmpty);
  });

  testWidgets("l'écran bloquant s'affiche en français et ne se ferme pas avec Retour", (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        locale: Locale('fr'),
        localizationsDelegates: [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: [Locale('fr'), Locale('ar')],
        home: EcranMiseAJourRequise(
          info: InfoMiseAJourRequise(
            message: 'Mise à jour requise',
            versionMinimale: '1.3.0',
            urlTelechargement: 'https://exemple.test/app.apk',
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Mise à jour requise'), findsOneWidget);
    expect(find.textContaining('Version minimale : 1.3.0'), findsOneWidget);
    expect(find.text('Mettre à jour'), findsOneWidget);

    // Le bouton Retour du système ne doit pas fermer l'écran
    final popScope = tester.widget<PopScope>(find.byType(PopScope));
    expect(popScope.canPop, isFalse);
  });

  testWidgets("l'écran s'affiche aussi en arabe", (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        locale: Locale('ar'),
        localizationsDelegates: [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: [Locale('fr'), Locale('ar')],
        home: EcranMiseAJourRequise(
          info: InfoMiseAJourRequise(message: '', versionMinimale: '1.3.0'),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('التحديث مطلوب'), findsOneWidget);
    // Sans lien de téléchargement, pas de bouton
    expect(find.byType(ElevatedButton), findsNothing);
  });
}
