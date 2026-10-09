import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../core/storage/storage_service.dart';
import '../core/theme/app_theme.dart';
import '../models/video_model.dart';

/// Carte vidéo moderne inspirée des vignettes Netflix.
class VideoCard extends StatelessWidget {
  final VideoModel video;
  final VoidCallback onTap;
  final double width;
  final double height;
  final bool showProgress;

  const VideoCard({
    super.key,
    required this.video,
    required this.onTap,
    this.width = 150,
    this.height = 210,
    this.showProgress = false,
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
            width: width,
            height: height,
            margin: const EdgeInsets.only(right: 12),
            decoration: BoxDecoration(
              color: AppTheme.netflixCard,
              borderRadius: BorderRadius.circular(6),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.4),
                  blurRadius: 6,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: Stack(
                fit: StackFit.expand,
                children: [
                  // 1. Miniature vidéo mise en cache
                  thumbUrl != null
                      ? CachedNetworkImage(
                          imageUrl: thumbUrl,
                          fit: BoxFit.cover,
                          placeholder: (context, url) => Container(
                            color: const Color(0xFF1F1F1F),
                            child: const Center(
                              child: SizedBox(
                                width: 24,
                                height: 24,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: AppTheme.netflixRed,
                                ),
                              ),
                            ),
                          ),
                          errorWidget: (context, url, error) => Container(
                            color: const Color(0xFF1F1F1F),
                            child: const Center(
                              child: Icon(Icons.movie, size: 40, color: Colors.white24),
                            ),
                          ),
                        )
                      : Container(
                          color: const Color(0xFF1F1F1F),
                          child: const Center(
                            child: Icon(Icons.play_circle_fill, size: 48, color: Colors.white30),
                          ),
                        ),

                  // 2. Dégradé sombre en bas pour la lisibilité
                  Positioned.fill(
                    child: Container(
                      decoration: const BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            Colors.transparent,
                            Colors.transparent,
                            Color(0xCC000000),
                            Colors.black,
                          ],
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                        ),
                      ),
                    ),
                  ),

                  // 3. Badge Catégorie en haut à gauche
                  Positioned(
                    top: 6,
                    left: 6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.7),
                        borderRadius: BorderRadius.circular(3),
                        border: Border.all(color: Colors.white12),
                      ),
                      child: Text(
                        video.category,
                        style: const TextStyle(
                          color: AppTheme.netflixWhite,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),

                  // 4. Durée en bas à droite
                  Positioned(
                    bottom: showProgress ? 12 : 8,
                    right: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.8),
                        borderRadius: BorderRadius.circular(3),
                      ),
                      child: Text(
                        video.formattedDuration,
                        style: const TextStyle(
                          color: Colors.white70,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),

                  // 5. Titre de la vidéo en bas
                  Positioned(
                    left: 8,
                    right: 8,
                    bottom: showProgress ? 12 : 8,
                    child: Text(
                      video.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),

                  // 6. Barre de progression rouge style Netflix ("Continuer la lecture")
                  if (showProgress && video.watchProgressSeconds > 0)
                    Positioned(
                      left: 0,
                      right: 0,
                      bottom: 0,
                      child: Container(
                        height: 4,
                        color: Colors.white12,
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: FractionallySizedBox(
                            widthFactor: video.progressFraction,
                            child: Container(
                              color: AppTheme.netflixRed,
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
