import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:google_mobile_ads/google_mobile_ads.dart';

import 'core/ads/ads_config.dart';
import 'core/erreurs/suivi_erreurs.dart';
import 'core/ads/consent_manager.dart';
import 'core/ads/rewarded_ad_service.dart';
import 'core/ads/watch_gate_controller.dart';
import 'core/localization/app_localizations.dart';
import 'core/navigation/app_route_observer.dart';
import 'core/theme/app_theme.dart';
import 'providers/locale_provider.dart';
import 'screens/splash/splash_screen.dart';

/// Riverpod 3 relance automatiquement un provider en erreur. Désactivé pour garder le
/// comportement de la version 1.2 (les écrans gèrent eux-mêmes « Réessayer »).
Duration? sansNouvelleTentativeAutomatique(int tentative, Object erreur) => null;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Capture globale des erreurs (console aujourd'hui, Crashlytics une fois Firebase configuré)
  SuiviErreurs.installer();

  // Initialisations AdMob réservées aux plateformes mobiles (Android/iOS)
  if (!kIsWeb) {
    MobileAds.instance.initialize().then((_) {
      if (AdsConfig.testDeviceIds.isNotEmpty) {
        MobileAds.instance.updateRequestConfiguration(
          RequestConfiguration(testDeviceIds: AdsConfig.testDeviceIds),
        );
      }
      ConsentManager.instance.requestConsent().catchError((e) {
        debugPrint('[Main] Erreur consentement: $e');
        return true;
      });
      WatchGateController.instance.initialize().catchError((_) {});
      RewardedAdService.instance.preloadAd();
    }).catchError((e) {
      debugPrint('[Main] Initialisation AdMob ignorée: $e');
    });
  } else {
    WatchGateController.instance.initialize().catchError((_) {});
  }

  // Barre d'état transparente pour un rendu plein écran cinéma
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: AppTheme.netflixBlack,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  runApp(
    const ProviderScope(
      retry: sansNouvelleTentativeAutomatique,
      child: VidTeleApp(),
    ),
  );
}

class VidTeleApp extends ConsumerWidget {
  final Duration? splashMinDuration;

  const VidTeleApp({super.key, this.splashMinDuration});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentLocale = ref.watch(localeProvider);

    return MaterialApp(
      title: 'Atlas Play',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.getDarkTheme(currentLocale),
      locale: currentLocale,
      navigatorObservers: [appRouteObserver],
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: const [
        Locale('fr', ''), // Français (LTR)
        Locale('en', ''), // English (LTR)
        Locale('ar', ''), // العربية (RTL)
      ],
      home: SplashScreen(
        minDuration: splashMinDuration ?? const Duration(milliseconds: 1200),
      ),
    );
  }
}
