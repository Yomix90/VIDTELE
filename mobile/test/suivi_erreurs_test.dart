import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vidtele_mobile/core/erreurs/suivi_erreurs.dart';

/// Rapporteur de test : mémorise les erreurs reçues.
class RapporteurMemoire extends RapporteurErreurs {
  final erreurs = <(Object, bool)>[];
  final notes = <String>[];

  @override
  Future<void> signaler(Object erreur, StackTrace? pile, {bool fatale = false, String? contexte}) async {
    erreurs.add((erreur, fatale));
  }

  @override
  void noter(String message) => notes.add(message);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('les erreurs du framework et les erreurs asynchrones sont transmises', () {
    final ancienFlutter = FlutterError.onError;
    final ancienPlateforme = PlatformDispatcher.instance.onError;
    final memoire = RapporteurMemoire();
    try {
      FlutterError.onError = (_) {}; // évite l'échec du test par le gestionnaire par défaut
      SuiviErreurs.installer(rapporteur: memoire);

      FlutterError.reportError(FlutterErrorDetails(exception: StateError('rendu')));
      final traitee = PlatformDispatcher.instance.onError!(StateError('async'), StackTrace.current);
      SuiviErreurs.noter('lecture vidéo 42');

      expect(traitee, isTrue);
      expect(memoire.erreurs.map((e) => '${e.$1}'), ['Bad state: rendu', 'Bad state: async']);
      expect(memoire.erreurs.map((e) => e.$2), [false, true]);
      expect(memoire.notes, ['lecture vidéo 42']);
    } finally {
      FlutterError.onError = ancienFlutter;
      PlatformDispatcher.instance.onError = ancienPlateforme;
    }
  });
}
