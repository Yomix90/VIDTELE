import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../constants/api_constants.dart';

/// Service de persistance locale : tokens JWT sécurisés et préférences utilisateur.
class StorageService {
  // Les versions <= 1.2.0 stockaient les jetons avec EncryptedSharedPreferences (v9).
  // La v10 détecte ces données et les migre au premier accès (migrateOnAlgorithmChange) :
  // l'utilisateur reste connecté après la mise à jour.
  // ATTENTION : ne PAS activer migrateWithBackup. Avec cette option, la v10.3.4 saute la
  // migration depuis EncryptedSharedPreferences (vérifié sur émulateur : jetons perdus,
  // utilisateur déconnecté).
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage(
    aOptions: AndroidOptions(migrateOnAlgorithmChange: true),
  );

  // -------------------------------------------------------------
  // Gestion des Tokens JWT (Stockage Sécurisé Chiffré)
  // -------------------------------------------------------------

  Future<String?> getAccessToken() async {
    return await _secureStorage.read(key: ApiConstants.keyAccessToken);
  }

  Future<void> setAccessToken(String token) async {
    await _secureStorage.write(key: ApiConstants.keyAccessToken, value: token);
  }

  Future<String?> getRefreshToken() async {
    return await _secureStorage.read(key: ApiConstants.keyRefreshToken);
  }

  Future<void> setRefreshToken(String token) async {
    await _secureStorage.write(key: ApiConstants.keyRefreshToken, value: token);
  }

  Future<void> clearAuthData() async {
    await _secureStorage.delete(key: ApiConstants.keyAccessToken);
    await _secureStorage.delete(key: ApiConstants.keyRefreshToken);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(ApiConstants.keyUser);
  }

  // -------------------------------------------------------------
  // Préférences Générales (URL Serveur, Langue)
  // -------------------------------------------------------------

  Future<String> getServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(ApiConstants.keyServerUrl) ?? ApiConstants.defaultBaseUrl;
  }

  Future<void> setServerUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    // Normaliser l'URL (retirer le slash final si présent)
    final cleanUrl = url.trim().endsWith('/') ? url.trim().substring(0, url.trim().length - 1) : url.trim();
    await prefs.setString(ApiConstants.keyServerUrl, cleanUrl);
  }

  Future<String> getLanguage() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(ApiConstants.keyLanguage) ?? 'fr';
  }

  Future<void> setLanguage(String lang) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(ApiConstants.keyLanguage, lang);
  }

  // -------------------------------------------------------------
  // Préférences de Lecture Vidéo (Masquage Automatique, Rotation)
  // -------------------------------------------------------------

  Future<bool> getAutoHideControls() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool('vidtele_auto_hide_controls') ?? true;
  }

  Future<void> setAutoHideControls(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('vidtele_auto_hide_controls', enabled);
  }

  Future<int> getAutoHideSeconds() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt('vidtele_auto_hide_seconds') ?? 3;
  }

  Future<void> setAutoHideSeconds(int seconds) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('vidtele_auto_hide_seconds', seconds);
  }
}

final storageService = StorageService();
