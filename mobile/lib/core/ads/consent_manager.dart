import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';

/// Gestionnaire de consentement utilisateur (Google User Messaging Platform - UMP).
///
/// Indispensable pour la conformité avec le RGPD (Europe), le DMA et les règles Google Play / AdMob.
/// Vérifie l'état du consentement, affiche le formulaire officiel Google si requis,
/// et détermine si l'application est légalement autorisée à demander des annonces.
class ConsentManager {
  static final ConsentManager instance = ConsentManager._internal();
  ConsentManager._internal();

  /// Initialise la demande de mise à jour des informations de consentement et
  /// présente le formulaire si requis par la réglementation locale.
  Future<bool> requestConsent() async {
    final completer = Completer<bool>();

    final params = ConsentRequestParameters(
      consentDebugSettings: kDebugMode
          ? ConsentDebugSettings(
              debugGeography: DebugGeography.debugGeographyEea,
            )
          : null,
    );

    ConsentInformation.instance.requestConsentInfoUpdate(
      params,
      () async {
        // Chargement et affichage du formulaire UMP si nécessaire
        ConsentForm.loadAndShowConsentFormIfRequired((formError) async {
          if (formError != null) {
            debugPrint('[ConsentManager] Erreur affichage formulaire: ${formError.message}');
          }

          final canRequest = await ConsentInformation.instance.canRequestAds();
          completer.complete(canRequest);
        });
      },
      (formError) {
        debugPrint('[ConsentManager] Échec mise à jour consentement: ${formError.message}');
        // En cas d'erreur réseau, vérifier si les annonces peuvent quand même être demandées
        ConsentInformation.instance.canRequestAds().then((can) {
          completer.complete(can);
        }).catchError((_) {
          completer.complete(true);
        });
      },
    );

    return completer.future;
  }

  /// Vérifie si l'application peut requêter des annonces
  Future<bool> canRequestAds() async {
    try {
      return await ConsentInformation.instance.canRequestAds();
    } catch (_) {
      return true;
    }
  }

  /// Permet à l'utilisateur de révoquer ou modifier ses choix de consentement
  /// depuis l'écran des paramètres de l'application
  Future<void> showPrivacyOptionsForm() async {
    ConsentForm.showPrivacyOptionsForm((formError) {
      if (formError != null) {
        debugPrint('[ConsentManager] Erreur options de confidentialité: ${formError.message}');
      }
    });
  }

  /// Réinitialise l'état de consentement (utile en phase de test)
  Future<void> reset() async {
    await ConsentInformation.instance.reset();
  }
}
