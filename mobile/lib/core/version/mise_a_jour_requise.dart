import 'package:flutter/foundation.dart';

/// Informations renvoyées par le serveur avec une réponse 426 « Mise à jour requise ».
@immutable
class InfoMiseAJourRequise {
  final String message;
  final String versionMinimale;
  final String? urlTelechargement;

  const InfoMiseAJourRequise({
    required this.message,
    required this.versionMinimale,
    this.urlTelechargement,
  });

  /// Construit l'information depuis le corps JSON de la réponse 426.
  factory InfoMiseAJourRequise.depuisJson(Object? donnees) {
    final json = donnees is Map ? donnees : const {};
    final url = json['download_url'];
    return InfoMiseAJourRequise(
      message: (json['detail'] ?? 'Une nouvelle version est nécessaire pour continuer.').toString(),
      versionMinimale: (json['min_version'] ?? '').toString(),
      urlTelechargement: url is String && url.isNotEmpty ? url : null,
    );
  }
}

/// Signal global : non nul dès qu'une requête a reçu 426.
/// L'application affiche alors l'écran bloquant de mise à jour par-dessus tout.
final ValueNotifier<InfoMiseAJourRequise?> miseAJourRequise = ValueNotifier(null);
