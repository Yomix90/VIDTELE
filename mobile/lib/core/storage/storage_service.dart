import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../constants/api_constants.dart';

/// Service de persistance locale : tokens JWT sécurisés et préférences utilisateur.
class StorageService {
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
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
}

final storageService = StorageService();
