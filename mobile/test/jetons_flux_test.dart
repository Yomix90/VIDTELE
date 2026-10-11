import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:vidtele_mobile/core/api/api_client.dart';
import 'package:vidtele_mobile/core/services/jetons_flux.dart';

/// Adaptateur HTTP simulé : délivre un jeton numéroté par appel, ou échoue.
class AdaptateurSimule implements HttpClientAdapter {
  int appels = 0;
  bool enPanne = false;

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    appels++;
    if (enPanne) {
      return ResponseBody.fromString('{"detail":"panne"}', 500, headers: {
        Headers.contentTypeHeader: ['application/json'],
      });
    }
    final corps = jsonEncode({'stream_token': 'jeton-$appels', 'video_id': 7});
    return ResponseBody.fromString(corps, 200, headers: {
      Headers.contentTypeHeader: ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late AdaptateurSimule adaptateur;

  setUp(() {
    SharedPreferences.setMockInitialValues({'vidtele_server_url': 'https://serveur.test'});
    FlutterSecureStorage.setMockInitialValues({'vidtele_access_token': 'jeton-acces'});
    adaptateur = AdaptateurSimule();
    apiClient.dio.httpClientAdapter = adaptateur;
    JetonsFlux.instance.viderPourTest();
  });

  test('URL avec jeton de flux dédié, réutilisé tant qu\'il est valide', () async {
    final url1 = await JetonsFlux.instance.urlFlux(7);
    final url2 = await JetonsFlux.instance.urlFlux(7);

    expect(url1.toString(), 'https://serveur.test/api/videos/7/stream?token=jeton-1');
    expect(url2, url1);
    expect(adaptateur.appels, 1, reason: 'un seul appel réseau pour deux lectures');
    expect(url1.toString(), isNot(contains('jeton-acces')), reason: "plus de jeton d'accès dans l'URL");
  });

  test('renouvellement forcé lors d\'une reprise après erreur', () async {
    await JetonsFlux.instance.urlFlux(7);
    final url = await JetonsFlux.instance.urlFlux(7, renouveler: true);
    expect(url.queryParameters['token'], 'jeton-2');
  });

  test('demandes simultanées regroupées en une seule requête', () async {
    await Future.wait([for (var i = 0; i < 3; i++) JetonsFlux.instance.urlFlux(9)]);
    expect(adaptateur.appels, 1);
  });

  test("repli sur le jeton d'accès si le serveur ne délivre pas de jeton de flux", () async {
    adaptateur.enPanne = true;
    final url = await JetonsFlux.instance.urlFlux(7);
    expect(url.queryParameters['token'], 'jeton-acces');
  });

  test('identifiant de session stable et en-têtes du lecteur sans jeton', () {
    final entetes = JetonsFlux.instance.entetesLecteur;
    expect(entetes['X-Session-ID'], hasLength(32));
    expect(JetonsFlux.instance.entetesLecteur['X-Session-ID'], entetes['X-Session-ID']);
    expect(entetes.containsKey('Authorization'), isFalse);
    expect(entetes['X-App-Version'], isNotEmpty);
  });
}
