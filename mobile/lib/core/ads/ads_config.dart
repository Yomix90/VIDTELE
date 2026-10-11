import 'package:flutter/foundation.dart';

/// Configuration centralisée de la monétisation Google AdMob pour Atlas Play.
///
/// Sécurisé contre les suspensions AdMob :
/// - Utilise les IDs de test officiels Google hors version publiée (`!kReleaseMode` : debug et profile)
/// - Utilise les IDs réels AdMob de l'utilisateur uniquement en mode release
/// - Permet d'enregistrer des identifiants d'appareils de test pour protéger le compte
class AdsConfig {
  // ==================== IDENTIFIANTS OFFICIELS PRODUCTION ====================
  static const String admobAppIdAndroidProd = 'ca-app-pub-7846348811801616~6697457552';
  static const String rewardedAdUnitIdAndroidProd = 'ca-app-pub-7846348811801616/7954698905';

  // ==================== IDENTIFIANTS OFFICIELS DE TEST ====================
  static const String admobAppIdAndroidTest = 'ca-app-pub-3940256099942544~3347511713';
  static const String rewardedAdUnitIdAndroidTest = 'ca-app-pub-3940256099942544/5224354917';

  // ==================== APPAREILS DE TEST ====================
  // Ajouter ici les identifiants d'appareils de test affichés dans Logcat/Console
  // pour s'assurer que même en release, aucune annonce réelle n'enregistre de clics frauduleux.
  static const List<String> testDeviceIds = [
    // ex: "33BE2250B43518CCDA7DE426D04EE231"
  ];

  /// Identifiant d'application AdMob actif
  static String get admobAppId {
    if (!kReleaseMode) {
      return admobAppIdAndroidTest;
    }
    return admobAppIdAndroidProd;
  }

  /// Identifiant du bloc vidéo avec récompense (Rewarded) actif
  static String get rewardedAdUnitId {
    if (!kReleaseMode) {
      return rewardedAdUnitIdAndroidTest;
    }
    return rewardedAdUnitIdAndroidProd;
  }

  /// Indique si les annonces fonctionnent avec les blocs de test
  // Annonces de test hors version publiée (debug ET profile) : afficher de vraies annonces
  // pendant des tests sur téléphone peut faire suspendre le compte AdMob (trafic invalide).
  static bool get isTestMode => !kReleaseMode;
}
