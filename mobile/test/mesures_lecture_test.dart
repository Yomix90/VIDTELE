import 'package:flutter_test/flutter_test.dart';
import 'package:video_player/video_player.dart';
import 'package:vidtele_mobile/core/services/mesures_lecture.dart';

/// Contrôleur simulé dont on pilote l'état (sans lecteur natif).
class ControleurSimule extends VideoPlayerController {
  ControleurSimule() : super.networkUrl(Uri.parse('https://exemple.test/v.mp4')) {
    value = const VideoPlayerValue(duration: Duration(seconds: 60), isInitialized: true);
  }

  void etat({bool? lecture, Duration? position, bool? tampon}) {
    value = value.copyWith(isPlaying: lecture, position: position, isBuffering: tampon);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final mesures = MesuresLecture.instance;

  setUp(mesures.reinitialiserPourTest);

  test('temps jusqu\'à la première image mesuré depuis l\'affichage', () async {
    final c = ControleurSimule();
    mesures.focus(42);
    await Future<void>.delayed(const Duration(milliseconds: 120));
    mesures.suivre(42, c, precharge: false);
    c.etat(lecture: true); // lecture demandée, pas encore d'image
    expect(mesures.enAttente, isEmpty);

    c.etat(position: const Duration(milliseconds: 40)); // première image
    c.etat(position: const Duration(milliseconds: 80)); // une seule mesure par affichage

    expect(mesures.enAttente, hasLength(1));
    final e = mesures.enAttente.single;
    expect(e['type'], 'demarrage');
    expect(e['video_id'], 42);
    expect(e['precharge'], false);
    expect(e['ttff_ms'] as int, greaterThanOrEqualTo(120));
  });

  test('reprise sans départ enregistré : pas compté comme un démarrage', () {
    final c = ControleurSimule();
    mesures.suivre(3, c, precharge: true); // ex. retour d'arrière-plan
    c.etat(lecture: true, position: const Duration(seconds: 5));
    expect(mesures.enAttente, isEmpty);
  });

  test('vidéo préchargée déjà en lecture : mesure immédiate', () {
    final c = ControleurSimule()..etat(lecture: true, position: const Duration(seconds: 1));
    mesures.focus(7);
    mesures.suivre(7, c, precharge: true);
    expect(mesures.enAttente.single['precharge'], true);
  });

  test('blocages : seuls ceux de plus de 300 ms sont comptés', () async {
    final c = ControleurSimule();
    mesures.focus(9);
    mesures.suivre(9, c, precharge: true);
    c.etat(lecture: true, position: const Duration(seconds: 1)); // première image

    c.etat(tampon: true);
    c.etat(tampon: false); // micro-blocage ignoré

    c.etat(tampon: true);
    await Future<void>.delayed(const Duration(milliseconds: 350));
    c.etat(tampon: false);

    final blocages = mesures.enAttente.where((e) => e['type'] == 'blocage').toList();
    expect(blocages, hasLength(1));
    expect(blocages.single['stall_ms'] as int, greaterThanOrEqualTo(300));
  });

  test('le lecteur précédent n\'est plus suivi après un changement de vidéo', () {
    final ancien = ControleurSimule();
    final nouveau = ControleurSimule();
    mesures.focus(1);
    mesures.suivre(1, ancien, precharge: true);
    mesures.suivre(2, nouveau, precharge: true);
    ancien.etat(lecture: true, position: const Duration(seconds: 1));
    expect(mesures.enAttente, isEmpty);
  });

  test('reprise et erreur enregistrées', () {
    mesures.reprise(5, tentative: 2, positionS: 12.5);
    mesures.erreur(5, 'lecture_impossible');
    expect(mesures.enAttente.map((e) => e['type']), ['reprise', 'erreur']);
    expect(mesures.enAttente.last['code_erreur'], 'lecture_impossible');
  });
}
