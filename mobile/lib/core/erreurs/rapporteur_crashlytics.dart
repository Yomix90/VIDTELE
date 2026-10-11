import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';

import 'suivi_erreurs.dart';

/// Envoie les erreurs et plantages à Firebase Crashlytics.
///
/// Confidentialité : seul l'identifiant technique de l'utilisateur est associé aux
/// rapports (jamais le nom, l'e-mail ni les jetons). La collecte est désactivée en debug.
class RapporteurCrashlytics extends RapporteurErreurs {
  final FirebaseCrashlytics _crashlytics;

  RapporteurCrashlytics._(this._crashlytics);

  /// Initialise Firebase et renvoie le rapporteur, ou null si Firebase n'est pas
  /// configuré (google-services.json absent, web, tests) : l'app continue alors
  /// avec le rapporteur console.
  static Future<RapporteurCrashlytics?> initialiser() async {
    if (kIsWeb) return null;
    try {
      await Firebase.initializeApp();
      final crashlytics = FirebaseCrashlytics.instance;
      await crashlytics.setCrashlyticsCollectionEnabled(!kDebugMode);
      return RapporteurCrashlytics._(crashlytics);
    } catch (e) {
      debugPrint('[Crashlytics] Non configuré, suivi local uniquement : $e');
      return null;
    }
  }

  @override
  Future<void> signaler(Object erreur, StackTrace? pile, {bool fatale = false, String? contexte}) async {
    if (kDebugMode) debugPrint('[Erreur${fatale ? ' FATALE' : ''}] $erreur');
    await _crashlytics.recordError(erreur, pile, fatal: fatale, reason: contexte);
  }

  @override
  Future<void> definirUtilisateur(String? identifiant) => _crashlytics.setUserIdentifier(identifiant ?? '');

  @override
  void noter(String message) => _crashlytics.log(message);
}
