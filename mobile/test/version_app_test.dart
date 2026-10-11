import 'package:flutter_test/flutter_test.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:vidtele_mobile/core/version/version_app.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('la version est lue dans le paquet installé (et non écrite en dur)', () async {
    PackageInfo.setMockInitialValues(
      appName: 'Atlas Play',
      packageName: 'com.vidtele.app',
      version: '1.3.0',
      buildNumber: '2004',
      buildSignature: '',
    );
    await VersionApp.charger();
    expect(VersionApp.actuelle, '1.3.0');
  });

  test('valeur de repli si la version est vide', () async {
    VersionApp.definirPourTest(VersionApp.versionParDefaut);
    PackageInfo.setMockInitialValues(
      appName: 'Atlas Play',
      packageName: 'com.vidtele.app',
      version: '',
      buildNumber: '',
      buildSignature: '',
    );
    await VersionApp.charger();
    expect(VersionApp.actuelle, VersionApp.versionParDefaut);
  });
}
