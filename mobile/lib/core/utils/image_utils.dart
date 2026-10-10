/// Utilitaire centralisé pour la résolution sécurisée des URLs d'images et affiches (posters).
class ImageUtils {
  /// Résout l'URL complète d'une image qu'elle soit absolue (http/https) ou relative (/static/...)
  static String? resolveUrl(String? path, String baseUrl) {
    if (path == null) return null;
    final clean = path.trim();
    if (clean.isEmpty) return null;

    // Déjà une URL absolue (TMDB, CDN externe, ou URL complète)
    if (clean.startsWith('http://') || clean.startsWith('https://')) {
      return clean;
    }

    // URL relative sur le serveur VPS
    final base = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    final relative = clean.startsWith('/') ? clean : '/$clean';
    return '$base$relative';
  }
}
