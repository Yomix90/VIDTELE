import 'dart:async';

import 'package:flutter/foundation.dart';

/// Destination des erreurs (Crashlytics en production, journal en développement).
///
/// Le reste de l'application ne dépend que de cette interface : brancher
/// Firebase Crashlytics (ou un autre outil) ne modifie aucun écran.
abstract class RapporteurErreurs {
  Future<void> signaler(
    Object erreur,
    StackTrace? pile, {
    bool fatale = false,
    String? contexte,
  });

  /// Associe les rapports suivants à un utilisateur (identifiant technique uniquement,
  /// jamais de nom ni d'e-mail).
  Future<void> definirUtilisateur(String? identifiant) async {}

  /// Fil d'Ariane : derniers événements avant un plantage (ex. « lecture vidéo 42 »).
  void noter(String message) {}
}

/// Rapporteur par défaut : écrit dans la console (debugPrint), aucun envoi réseau.
class RapporteurConsole extends RapporteurErreurs {
  @override
  Future<void> signaler(Object erreur, StackTrace? pile, {bool fatale = false, String? contexte}) async {
    debugPrint('[Erreur${fatale ? ' FATALE' : ''}${contexte != null ? ' • $contexte' : ''}] $erreur');
    if (pile != null && kDebugMode) debugPrint('$pile');
  }

  @override
  void noter(String message) => debugPrint('[Trace] $message');
}

/// Point d'entrée unique du suivi des erreurs et plantages.
class SuiviErreurs {
  SuiviErreurs._();

  static RapporteurErreurs _rapporteur = RapporteurConsole();

  static RapporteurErreurs get rapporteur => _rapporteur;

  /// Installe la capture globale. À appeler au tout début de main().
  static void installer({RapporteurErreurs? rapporteur}) {
    if (rapporteur != null) _rapporteur = rapporteur;

    // Erreurs du framework (construction, mise en page, rendu)
    final precedent = FlutterError.onError;
    FlutterError.onError = (details) {
      precedent?.call(details);
      _rapporteur.signaler(
        details.exception,
        details.stack,
        fatale: false,
        contexte: details.context?.toDescription(),
      );
    };

    // Erreurs asynchrones non interceptées (Future sans catch, plugins natifs...)
    PlatformDispatcher.instance.onError = (erreur, pile) {
      _rapporteur.signaler(erreur, pile, fatale: true);
      return true; // traitée : l'application continue au lieu de s'arrêter
    };
  }

  /// Signalement explicite d'une erreur interceptée mais importante
  /// (ex. échec répété de lecture vidéo).
  static Future<void> signaler(Object erreur, [StackTrace? pile, String? contexte]) =>
      _rapporteur.signaler(erreur, pile ?? StackTrace.current, contexte: contexte);

  static void noter(String message) => _rapporteur.noter(message);

  static Future<void> definirUtilisateur(String? identifiant) => _rapporteur.definirUtilisateur(identifiant);
}
