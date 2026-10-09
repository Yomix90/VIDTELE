import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../core/storage/storage_service.dart';
import '../core/theme/app_theme.dart';
import '../models/video_model.dart';

/// Carte Top 5 avec numéro géant stylisé à la Netflix.
class TopNumberCard extends StatelessWidget {
  final int rank;
  final VideoModel video;
  final VoidCallback onTap;

  const TopNumberCard({
    super.key,
    required this.rank,
    required this.video,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String>(
      future: storageService.getServerUrl(),
      builder: (context, snapshot) {
        final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;
        final thumbUrl = video.thumbnailPath != null ? '$baseUrl${video.thumbnailPath}' : null;

        return GestureDetector(
          onTap: onTap,
          child: Container(
            width: 175,
            height: 200,
            margin: const EdgeInsets.only(right: 8),
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                // 1. Chiffre géant calligraphié Netflix (Arrière-plan gauche)
                Positioned(
                  left: 0,
                  bottom: -15,
                  child: Stack(
                    children: [
                      // Contour extérieur épais
                      Text(
                        '$rank',
                        style: TextStyle(
                          fontSize: 105,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -10,
                          foreground: Paint()
                            ..style = PaintingStyle.stroke
                            ..strokeWidth = 6
                            ..color = const Color(0xFF595959),
                        ),
                      ),
                      // Remplissage sombre intérieur
                      Text(
                        '$rank',
                        style: const TextStyle(
                          fontSize: 105,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -10,
                          color: Color(0xFF0F0F0F),
                        ),
                      ),
                    ],
                  ),
                ),

                // 2. Affiche vidéo (Alignée à droite du chiffre géant)
                Positioned(
                  right: 0,
                  top: 0,
                  bottom: 0,
                  width: 125,
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppTheme.netflixCard,
                      borderRadius: BorderRadius.circular(6),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.5),
                          blurRadius: 8,
                          offset: const Offset(2, 4),
                        ),
                      ],
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(6),
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          thumbUrl != null
                              ? CachedNetworkImage(
                                  imageUrl: thumbUrl,
                                  fit: BoxFit.cover,
                                  placeholder: (context, url) => Container(color: const Color(0xFF1F1F1F)),
                                  errorWidget: (context, url, error) => const Icon(Icons.movie, color: Colors.white24),
                                )
                              : const Icon(Icons.movie, color: Colors.white24),

                          // Dégradé sombre
                          Positioned.fill(
                            child: Container(
                              decoration: const BoxDecoration(
                                gradient: LinearGradient(
                                  colors: [Colors.transparent, Colors.black87],
                                  begin: Alignment.topCenter,
                                  end: Alignment.bottomCenter,
                                ),
                              ),
                            ),
                          ),

                          // Titre
                          Positioned(
                            left: 6,
                            right: 6,
                            bottom: 6,
                            child: Text(
                              video.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
