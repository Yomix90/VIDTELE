import 'package:dio/dio.dart';
import '../constants/api_constants.dart';
import '../storage/storage_service.dart';
import '../version/mise_a_jour_requise.dart';
import '../version/version_app.dart';

/// Client HTTP Dio configuré avec intercepteur d'authentification JWT
/// et renouvellement automatique transparent en cas d'expiration de session (401).
class ApiClient {
  late final Dio dio;
  bool _isRefreshing = false;

  ApiClient() {
    dio = Dio(
      BaseOptions(
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    _setupInterceptors();
  }

  void _setupInterceptors() {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // 1. Mise à jour dynamique de la base URL
          final baseUrl = await storageService.getServerUrl();
          options.baseUrl = baseUrl;

          // Version de l'application : permet au serveur d'exiger une mise à jour (426)
          options.headers['X-App-Version'] = VersionApp.actuelle;

          // 2. Ajout automatique du Bearer token si présent
          final token = await storageService.getAccessToken();
          if (token != null && !options.headers.containsKey('Authorization')) {
            options.headers['Authorization'] = 'Bearer $token';
          }

          return handler.next(options);
        },
        onError: (DioException error, handler) async {
          // Version trop ancienne pour le serveur : écran bloquant de mise à jour
          if (error.response?.statusCode == 426) {
            miseAJourRequise.value = InfoMiseAJourRequise.depuisJson(error.response?.data);
            return handler.next(error);
          }

          // 3. Gestion du renouvellement automatique sur erreur 401
          if (error.response?.statusCode == 401 && !_isRefreshing) {
            final path = error.requestOptions.path;
            // Ne pas tenter de rafraîchir sur les routes de login ou de refresh elles-mêmes
            if (path != ApiConstants.login && path != ApiConstants.refresh) {
              _isRefreshing = true;
              try {
                final refreshToken = await storageService.getRefreshToken();
                if (refreshToken != null) {
                  final baseUrl = await storageService.getServerUrl();
                  final refreshDio = Dio(BaseOptions(baseUrl: baseUrl));
                  
                  final refreshRes = await refreshDio.post(
                    ApiConstants.refresh,
                    data: {'refresh_token': refreshToken},
                  );

                  if (refreshRes.statusCode == 200) {
                    final newAccessToken = refreshRes.data['access_token'];
                    final newRefreshToken = refreshRes.data['refresh_token'];

                    await storageService.setAccessToken(newAccessToken);
                    await storageService.setRefreshToken(newRefreshToken);

                    // Rejouer la requête initiale avec le nouveau token
                    final opts = error.requestOptions;
                    opts.headers['Authorization'] = 'Bearer $newAccessToken';
                    final cloneReq = await dio.fetch(opts);
                    _isRefreshing = false;
                    return handler.resolve(cloneReq);
                  }
                }
              } catch (e) {
                // Échec du renouvellement -> déconnexion
                await storageService.clearAuthData();
              } finally {
                _isRefreshing = false;
              }
            }
          }
          return handler.next(error);
        },
      ),
    );
  }
}

final apiClient = ApiClient();
