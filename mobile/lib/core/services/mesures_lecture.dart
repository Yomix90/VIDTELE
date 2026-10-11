import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:video_player/video_player.dart';

import '../api/api_client.dart';

/// Mesures de lecture envoyées au serveur (POST /api/analytics/playback) :
/// temps jusqu'à la première image, blocages, reprises et erreurs.
///
/// Les envois sont groupés (toutes les 30 s, dès 20 événements, ou au passage en
/// arrière-plan) et un échec d'envoi n'a jamais d'effet sur la lecture.
class MesuresLecture with WidgetsBindingObserver {
  MesuresLecture._() {
    WidgetsBinding.instance.addObserver(this);
  }

  static final MesuresLecture instance = MesuresLecture._();

  static const int tailleLot = 20;
  static const int maxEnAttente = 200;
  static const Duration intervalleEnvoi = Duration(seconds: 30);
  /// Un blocage plus court n'est pas significatif (simple remplissage du tampon)
  static const Duration blocageMinimal = Duration(milliseconds: 300);

  final List<Map<String, Object?>> _enAttente = [];
  final Map<int, DateTime> _focus = {};
  Timer? _minuterie;
  bool _envoiEnCours = false;

  // Suivi du lecteur courant
  VideoPlayerController? _controleur;
  VoidCallback? _ecouteur;

  /// La vidéo vient d'être affichée et sa lecture est demandée (swipe, ouverture).
  void focus(int videoId) => _focus[videoId] = DateTime.now();

  /// Comme [focus], sans écraser un départ déjà enregistré (première vidéo ouverte).
  void focusSiAbsent(int videoId) => _focus.putIfAbsent(videoId, DateTime.now);

  /// Suit le lecteur de la vidéo affichée : première image et blocages.
  void suivre(int videoId, VideoPlayerController controleur, {required bool precharge}) {
    _detacher();
    // Sans départ enregistré (reprise après l'arrière-plan, retour sur l'onglet déjà vu),
    // ce n'est pas un démarrage : on ne suit que les blocages.
    final depart = _focus.remove(videoId);
    var premiereImage = depart == null;
    DateTime? debutBlocage;

    void ecouter() {
      final v = controleur.value;
      if (!premiereImage) {
        if (v.isPlaying && v.position > Duration.zero) {
          premiereImage = true;
          _ajouter({
            'type': 'demarrage',
            'video_id': videoId,
            'ttff_ms': DateTime.now().difference(depart!).inMilliseconds,
            'precharge': precharge,
          });
        }
        return;
      }
      if (v.isBuffering && debutBlocage == null) {
        debutBlocage = DateTime.now();
      } else if (!v.isBuffering && debutBlocage != null) {
        final duree = DateTime.now().difference(debutBlocage!);
        debutBlocage = null;
        if (duree >= blocageMinimal) {
          _ajouter({
            'type': 'blocage',
            'video_id': videoId,
            'stall_ms': duree.inMilliseconds,
            'position_s': v.position.inMilliseconds / 1000,
          });
        }
      }
    }

    _controleur = controleur;
    _ecouteur = ecouter;
    controleur.addListener(ecouter);
    ecouter(); // déjà en lecture (lecteur préchargé) : mesure immédiate
  }

  void _detacher() {
    final c = _controleur;
    final e = _ecouteur;
    if (c != null && e != null) {
      try {
        c.removeListener(e);
      } catch (_) {
        // contrôleur déjà libéré
      }
    }
    _controleur = null;
    _ecouteur = null;
  }

  /// Le lecteur a été relancé automatiquement (watchdog).
  void reprise(int videoId, {required int tentative, double? positionS}) =>
      _ajouter({'type': 'reprise', 'video_id': videoId, 'position_s': positionS, 'code_erreur': 'tentative_$tentative'});

  /// Erreur définitive affichée à l'utilisateur.
  void erreur(int videoId, String code) =>
      _ajouter({'type': 'erreur', 'video_id': videoId, 'code_erreur': code.length > 64 ? code.substring(0, 64) : code});

  void _ajouter(Map<String, Object?> evenement) {
    evenement.removeWhere((_, valeur) => valeur == null);
    if (_enAttente.length >= maxEnAttente) _enAttente.removeAt(0);
    _enAttente.add(evenement);
    _minuterie ??= Timer.periodic(intervalleEnvoi, (_) => envoyer());
    if (_enAttente.length >= tailleLot) envoyer();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused || state == AppLifecycleState.hidden) envoyer();
  }

  /// Envoie les mesures en attente (sans effet si rien à envoyer ou envoi déjà en cours).
  Future<void> envoyer() async {
    if (_envoiEnCours || _enAttente.isEmpty) return;
    _envoiEnCours = true;
    final lot = List<Map<String, Object?>>.of(_enAttente.take(50));
    try {
      await apiClient.dio.post('/api/analytics/playback', data: {'evenements': lot});
      _enAttente.removeRange(0, lot.length);
    } catch (e) {
      // Serveur ancien (404), hors ligne... : on garde les mesures pour le prochain envoi
      debugPrint('[MesuresLecture] Envoi reporté : $e');
    } finally {
      _envoiEnCours = false;
    }
  }

  @visibleForTesting
  List<Map<String, Object?>> get enAttente => List.unmodifiable(_enAttente);

  @visibleForTesting
  void reinitialiserPourTest() {
    _detacher();
    _enAttente.clear();
    _focus.clear();
    _minuterie?.cancel();
    _minuterie = null;
  }
}
