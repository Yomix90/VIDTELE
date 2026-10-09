/// Constantes de configuration réseau et endpoints de l'API Atlas Play.
class ApiConstants {
  // URL par défaut du serveur VPS en production
  // Peut être modifiée dynamiquement dans l'application si nécessaire via les Paramètres.
  static const String defaultBaseUrl = 'https://vidtele.digitlab.dev';

  // Endpoint de mise à jour d'application
  static const String appVersion = '/api/app/version';

  // Endpoints Authentification
  static const String login = '/api/auth/login';
  static const String register = '/api/auth/register';
  static const String refresh = '/api/auth/refresh';
  static const String me = '/api/auth/me';

  // Endpoints Vidéos
  static const String videos = '/api/videos';
  static const String categories = '/api/videos/categories';
  static String videoDetail(int id) => '/api/videos/$id';
  static String videoThumbnail(int id) => '/api/videos/$id/thumbnail';
  static String videoStream(int id) => '/api/videos/$id/stream';
  static String videoStreamToken(int id) => '/api/videos/$id/stream-token';
  static String videoProgress(int id) => '/api/videos/$id/progress';
  static String videoStop(int id) => '/api/videos/$id/stream/stop';

  // Endpoints Bibliothèque
  static const String history = '/api/history';
  static const String favorites = '/api/favorites';
  static String favoriteAction(int id) => '/api/favorites/$id';

  // Clés de stockage sécurisé
  static const String keyAccessToken = 'vidtele_access_token';
  static const String keyRefreshToken = 'vidtele_refresh_token';
  static const String keyServerUrl = 'vidtele_server_url';
  static const String keyUser = 'vidtele_user_data';
  static const String keyLanguage = 'vidtele_language';
}
