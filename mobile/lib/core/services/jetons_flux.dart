import 'dart:math';

import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../constants/api_constants.dart';
import '../storage/storage_service.dart';
import '../version/version_app.dart';

/// URL de lecture d'une vidéo, avec un jeton de flux DÉDIÉ (lié à cette vidéo).
///
/// Avant (1.2.0) : le jeton d'accès du compte était placé dans l'URL du lecteur ; il
/// apparaissait dans les journaux et ouvrait toute l'API. Le jeton de flux, lui, n'ouvre
/// que la vidéo concernée et le serveur tolère son expiration pendant une lecture.
class JetonsFlux {
  JetonsFlux._();

  static final JetonsFlux instance = JetonsFlux._();

  /// Durée de réutilisation d'un jeton (le serveur le délivre pour 2 h, plus une tolérance).
  static const Duration dureeReutilisation = Duration(minutes: 90);

  /// Identifiant de session de lecture, stable pendant toute la vie de l'application :
  /// le serveur compte un appareil = un flux, quel que soit le nombre de lecteurs préchargés.
  final String idSession = _genererIdSession();

  final Map<int, (String, DateTime)> _cache = {};
  final Map<int, Future<String?>> _enCours = {};

  static String _genererIdSession() {
    final aleatoire = Random.secure();
    return List.generate(16, (_) => aleatoire.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
  }

  /// En-têtes envoyés par le lecteur vidéo (pas de jeton d'accès).
  Map<String, String> get entetesLecteur => {
        'X-Session-ID': idSession,
        'X-App-Version': VersionApp.actuelle,
      };

  /// URL complète du flux. [renouveler] force un nouveau jeton (reprise après erreur).
  Future<Uri> urlFlux(int videoId, {bool renouveler = false}) async {
    final baseUrl = await storageService.getServerUrl();
    final jeton = await _jeton(videoId, renouveler: renouveler);
    final requete = jeton != null ? '?token=${Uri.encodeQueryComponent(jeton)}' : '';
    return Uri.parse('$baseUrl${ApiConstants.videoStream(videoId)}$requete');
  }

  /// Prépare les jetons des vidéos suivantes en tâche de fond (évite une requête au swipe).
  void precharger(Iterable<int> videoIds) {
    for (final id in videoIds) {
      _jeton(id).ignore();
    }
  }

  void oublier(int videoId) => _cache.remove(videoId);

  Future<String?> _jeton(int videoId, {bool renouveler = false}) {
    if (!renouveler) {
      final enCache = _cache[videoId];
      if (enCache != null && DateTime.now().difference(enCache.$2) < dureeReutilisation) {
        return Future.value(enCache.$1);
      }
      final enCours = _enCours[videoId];
      if (enCours != null) return enCours;
    }
    // Accolades indispensables : « => _enCours.remove(...) » renverrait la requête elle-même,
    // que whenComplete attendrait alors indéfiniment (interblocage constaté en test).
    final demande = _demanderJeton(videoId).whenComplete(() {
      _enCours.remove(videoId);
    });
    _enCours[videoId] = demande;
    return demande;
  }

  Future<String?> _demanderJeton(int videoId) async {
    try {
      final res = await apiClient.dio.post(ApiConstants.videoStreamToken(videoId));
      final jeton = res.data is Map ? res.data['stream_token'] as String? : null;
      if (jeton != null && jeton.isNotEmpty) {
        _cache[videoId] = (jeton, DateTime.now());
        return jeton;
      }
    } catch (e) {
      debugPrint('[JetonsFlux] Jeton de flux indisponible pour $videoId : $e');
    }
    // Repli (serveur ancien ou erreur) : jeton d'accès, accepté par l'endpoint de flux
    return storageService.getAccessToken();
  }

  @visibleForTesting
  void viderPourTest() {
    _cache.clear();
    _enCours.clear();
  }
}
