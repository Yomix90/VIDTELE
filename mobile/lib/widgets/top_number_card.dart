import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../core/storage/storage_service.dart';
import '../core/theme/app_theme.dart';
import '../core/utils/image_utils.dart';
import '../models/home_model.dart';
import '../models/video_model.dart';
import 'touchable_scale.dart';

/// Carte Top 5 avec numéro géant stylisé à la Netflix et micro-zoom tactile.
class TopNumberCard extends StatelessWidget {
  final int rank;
  final String title;
  final String? posterPath;
  final double? rating;
  final VoidCallback onTap;
  final String? heroTag;

  const TopNumberCard({
    super.key,
    required this.rank,
    required this.title,
    this.posterPath,
    this.rating,
    required this.onTap,
    this.heroTag,
  });

  /// Constructeur rétro-compatible pour un `VideoModel`
  factory TopNumberCard.fromVideo({
    Key? key,
    required int rank,
    required VideoModel video,
    required VoidCallback onTap,
  }) {
    return TopNumberCard(
      key: key,
      rank: rank,
      title: video.title,
      posterPath: video.thumbnailPath,
      onTap: onTap,
      heroTag: 'top_video_${video.id}_$rank',
    );
  }

  /// Constructeur pour un `TopSeriesModel`
  factory TopNumberCard.fromSeries({
    Key? key,
    required int rank,
    required TopSeriesModel series,
    required VoidCallback onTap,
  }) {
    return TopNumberCard(
      key: key,
      rank: rank,
      title: series.title,
      posterPath: series.posterPath ?? series.bannerPath,
      rating: series.rating,
      onTap: onTap,
      heroTag: 'top_series_${series.id}_$rank',
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String>(
      future: storageService.getServerUrl(),
      builder: (context, snapshot) {
        final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;
        final thumbUrl = ImageUtils.resolveUrl(posterPath, baseUrl);

        return TouchableScale(
          onTap: onTap,
          child: Container(
            width: 175,
            height: 200,
            margin: const EdgeInsets.only(right: 8),
            child: Stack(
              clipBehavior: Clip.none,
              children: [
                // 1. Chiffre géant calligraphié Netflix (Arrière-plan start)
                Positioned.directional(
                  textDirection: Directionality.of(context),
                  start: 0,
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
                            ..color = const Color(0xFF4A4A58),
                        ),
                      ),
                      // Remplissage intérieur sombre
                      Text(
                        '$rank',
                        style: const TextStyle(
                          fontSize: 105,
                          fontWeight: FontWeight.w900,
                          letterSpacing: -10,
                          color: AppTheme.netflixBlack,
                        ),
                      ),
                    ],
                  ),
                ),

                // 2. Affiche vidéo / série (Alignée end)
                Positioned.directional(
                  textDirection: Directionality.of(context),
                  end: 0,
                  top: 0,
                  bottom: 0,
                  width: 125,
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppTheme.darkSurface,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.08),
                        width: 1,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.6),
                          blurRadius: 10,
                          offset: const Offset(2, 4),
                        ),
                      ],
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          if (thumbUrl != null && thumbUrl.isNotEmpty)
                            CachedNetworkImage(
                              imageUrl: thumbUrl,
                              fit: BoxFit.cover,
                              placeholder: (context, url) => Container(color: AppTheme.darkSurfaceLight),
                              errorWidget: (context, url, error) => Container(
                                color: AppTheme.darkSurfaceLight,
                                child: const Icon(Icons.tv, color: Colors.white24, size: 36),
                              ),
                            )
                          else
                            Container(
                              color: AppTheme.darkSurfaceLight,
                              child: const Icon(Icons.tv, color: Colors.white24, size: 36),
                            ),

                          // Dégradé sombre
                          Positioned.fill(
                            child: Container(
                              decoration: BoxDecoration(
                                gradient: LinearGradient(
                                  colors: [
                                    Colors.transparent,
                                    Colors.transparent,
                                    Colors.black.withValues(alpha: 0.85),
                                    Colors.black,
                                  ],
                                  stops: const [0.0, 0.4, 0.8, 1.0],
                                  begin: Alignment.topCenter,
                                  end: Alignment.bottomCenter,
                                ),
                              ),
                            ),
                          ),

                          // Badge Note si disponible
                          if (rating != null && rating! > 0)
                            Positioned(
                              top: 6,
                              right: 6,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.black.withValues(alpha: 0.8),
                                  borderRadius: BorderRadius.circular(4),
                                  border: Border.all(
                                    color: Colors.amber.withValues(alpha: 0.6),
                                    width: 0.8,
                                  ),
                                ),
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    const Icon(Icons.star, color: Colors.amber, size: 10),
                                    const SizedBox(width: 2),
                                    Text(
                                      rating!.toStringAsFixed(1),
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 9.5,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),

                          // Titre
                          Positioned(
                            left: 6,
                            right: 6,
                            bottom: 8,
                            child: Text(
                              title,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                shadows: [
                                  Shadow(color: Colors.black, blurRadius: 4),
                                ],
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
