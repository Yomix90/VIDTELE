import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:google_mobile_ads/google_mobile_ads.dart';

import 'core/ads/ads_config.dart';
import 'core/ads/consent_manager.dart';
import 'core/localization/app_localizations.dart';
import 'core/navigation/app_route_observer.dart';
import 'core/theme/app_theme.dart';
import 'providers/auth_provider.dart';
import 'providers/locale_provider.dart';
import 'screens/auth/login_screen.dart';
import 'screens/main_navigation_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 1. Initialisation de Google Mobile Ads et configuration des appareils de test
  try {
    await MobileAds.instance.initialize();
    if (AdsConfig.testDeviceIds.isNotEmpty) {
      await MobileAds.instance.updateRequestConfiguration(
        RequestConfiguration(testDeviceIds: AdsConfig.testDeviceIds),
      );
    }
    // 2. Demande de consentement UMP (Europe / RGPD) en arrière-plan
    ConsentManager.instance.requestConsent().catchError((e) {
      debugPrint('[Main] Erreur consentement: $e');
      return true;
    });
  } catch (e) {
    debugPrint('[Main] Initialisation AdMob ignorée/échouée: $e');
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
      child: VidTeleApp(),
    ),
  );
}

class VidTeleApp extends ConsumerWidget {
  const VidTeleApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
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
      home: authState.isLoading
          ? const Scaffold(
              backgroundColor: AppTheme.netflixBlack,
              body: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SizedBox(
                      width: 50,
                      height: 50,
                      child: CircularProgressIndicator(
                        color: AppTheme.netflixRed,
                        strokeWidth: 3,
                      ),
                    ),
                    SizedBox(height: 20),
                    Text(
                      'ATLAS PLAY',
                      style: TextStyle(
                        color: AppTheme.netflixRed,
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 3,
                      ),
                    ),
                  ],
                ),
              ),
            )
          : authState.isAuthenticated
              ? const MainNavigationScreen()
              : const LoginScreen(),
    );
  }
}
