import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';

/// Version réelle de l'application, lue dans l'APK (pubspec.yaml : `version:`).
///
/// Remplace l'ancienne constante écrite en dur ('1.2.0') qui n'était jamais mise
/// à jour. Utilisée pour la vérification des mises à jour au lancement et
/// envoyée au serveur dans l'en-tête `X-App-Version` (contrôle de version minimale).
class VersionApp {
  VersionApp._();

  /// Valeur de repli si la lecture échoue (tests, plateforme non prise en charge).
  static const String versionParDefaut = '1.2.0';

  static String _version = versionParDefaut;

  static String get actuelle => _version;

  /// À appeler une fois au démarrage, avant le premier appel réseau.
  static Future<void> charger() async {
    try {
      final info = await PackageInfo.fromPlatform();
      if (info.version.isNotEmpty) _version = info.version;
    } catch (e) {
      debugPrint('[VersionApp] Lecture de la version impossible : $e');
    }
  }

  @visibleForTesting
  static void definirPourTest(String version) => _version = version;
}
