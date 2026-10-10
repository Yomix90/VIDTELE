import 'dart:async';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/constants/api_constants.dart';
import '../core/localization/app_localizations.dart';
import '../core/storage/storage_service.dart';
import '../core/theme/app_theme.dart';
import '../core/utils/image_utils.dart';
import '../models/home_model.dart';
import '../screens/series/series_detail_screen.dart';
import 'touchable_scale.dart';

/// Slider Héro immersif avec défilement automatique toutes les 5s,
/// pause au toucher, indicateurs animés et boutons d'action style Netflix / ReelShort.
class HeroSlider extends ConsumerStatefulWidget {
  final List<HomeHeroItem> items;
  final void Function(HomeHeroItem item)? onWatch;

  const HeroSlider({
    super.key,
    required this.items,
    this.onWatch,
  });

  @override
  ConsumerState<HeroSlider> createState() => _HeroSliderState();
}

class _HeroSliderState extends ConsumerState<HeroSlider> {
  late final PageController _pageController;
  int _currentIndex = 0;
  Timer? _autoPlayTimer;
  bool _isUserTouching = false;

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
    _startAutoPlay();
  }

  @override
  void dispose() {
    _autoPlayTimer?.cancel();
    _pageController.dispose();
    super.dispose();
  }

  void _startAutoPlay() {
    _autoPlayTimer?.cancel();
    if (widget.items.length <= 1) return;

    _autoPlayTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (!_isUserTouching && mounted && _pageController.hasClients) {
        final nextIndex = (_currentIndex + 1) % widget.items.length;
        _pageController.animateToPage(
          nextIndex,
          duration: const Duration(milliseconds: 650),
          curve: Curves.easeInOutCubic,
        );
      }
    });
  }

  void _onUserTouchStart() {
    _isUserTouching = true;
  }

  void _onUserTouchEnd() {
    _isUserTouching = false;
  }

  @override
  Widget build(BuildContext context) {
    if (widget.items.isEmpty) return const SizedBox.shrink();

    final l10n = context.l10n;

    return FutureBuilder<String>(
      future: storageService.getServerUrl(),
      builder: (context, snapshot) {
        final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;

        return Listener(
          onPointerDown: (_) => _onUserTouchStart(),
          onPointerUp: (_) => _onUserTouchEnd(),
          onPointerCancel: (_) => _onUserTouchEnd(),
          child: SizedBox(
            height: 480,
            width: double.infinity,
            child: Stack(
              children: [
                // 1. PageView du Slider Héro
                PageView.builder(
                  controller: _pageController,
                  itemCount: widget.items.length,
                  onPageChanged: (idx) {
                    setState(() {
                      _currentIndex = idx;
                    });
                  },
                  itemBuilder: (context, index) {
                    final item = widget.items[index];
                    final posterUrl = ImageUtils.resolveUrl(
                      item.bannerPath ?? item.posterPath,
                      baseUrl,
                    );

                    return GestureDetector(
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => SeriesDetailScreen(
                              seriesId: item.id,
                              initialTitle: item.titleFr ?? item.title,
                              initialPoster: item.posterPath,
                            ),
                          ),
                        );
                      },
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          // Affiche d'arrière-plan avec Hero
                          Hero(
                            tag: 'series_banner_${item.id}',
                            child: posterUrl != null
                                ? CachedNetworkImage(
                                    imageUrl: posterUrl,
                                    fit: BoxFit.cover,
                                    alignment: Alignment.topCenter,
                                    placeholder: (context, url) => Container(
                                      color: AppTheme.darkSurface,
                                      child: const Center(
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: AppTheme.netflixRed,
                                        ),
                                      ),
                                    ),
                                    errorWidget: (context, url, error) => Container(
                                      color: AppTheme.darkSurface,
                                      child: const Icon(Icons.movie, size: 70, color: Colors.white24),
                                    ),
                                  )
                                : Container(
                                    color: AppTheme.darkSurface,
                                    child: const Icon(Icons.movie, size: 70, color: Colors.white24),
                                  ),
                          ),

                          // Dégradé cinématique immersif (haut transparent -> bas fond sombre)
                          Container(
                            decoration: const BoxDecoration(
                              gradient: LinearGradient(
                                colors: [
                                  Colors.transparent,
                                  Colors.transparent,
                                  Color(0x9909090C),
                                  Color(0xEE09090C),
                                  AppTheme.netflixBlack,
                                ],
                                stops: [0.0, 0.35, 0.65, 0.88, 1.0],
                                begin: Alignment.topCenter,
                                end: Alignment.bottomCenter,
                              ),
                            ),
                          ),

                          // Dégradé latéral subtil pour faire ressortir le texte
                          Container(
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [
                                  Colors.black.withValues(alpha: 0.4),
                                  Colors.transparent,
                                ],
                                stops: const [0.0, 0.6],
                                begin: Alignment.bottomLeft,
                                end: Alignment.topRight,
                              ),
                            ),
                          ),

                          // Contenu texte et badges
                          Positioned(
                            left: 20,
                            right: 20,
                            bottom: 60,
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.center,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                // Badge catégorie / micro-série
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: AppTheme.netflixRed.withValues(alpha: 0.9),
                                    borderRadius: BorderRadius.circular(4),
                                    boxShadow: [
                                      BoxShadow(
                                        color: AppTheme.netflixRed.withValues(alpha: 0.4),
                                        blurRadius: 8,
                                        offset: const Offset(0, 2),
                                      ),
                                    ],
                                  ),
                                  child: Text(
                                    item.category.toUpperCase(),
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 10.5,
                                      fontWeight: FontWeight.w900,
                                      letterSpacing: 1.5,
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 10),

                                // Titre de la série
                                Text(
                                  item.titleFr ?? item.title,
                                  textAlign: TextAlign.center,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 24,
                                    fontWeight: FontWeight.w900,
                                    letterSpacing: 0.4,
                                    shadows: [
                                      Shadow(color: Colors.black, blurRadius: 10, offset: Offset(0, 3)),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: 6),

                                // Métadonnées (Année, Note, Épisodes)
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    if (item.year != null) ...[
                                      Text(
                                        '${item.year}',
                                        style: const TextStyle(color: Colors.white70, fontSize: 12),
                                      ),
                                      const SizedBox(width: 8),
                                      const Text('•', style: TextStyle(color: Colors.white38)),
                                      const SizedBox(width: 8),
                                    ],
                                    if (item.rating != null && item.rating! > 0) ...[
                                      const Icon(Icons.star, color: Colors.amber, size: 13),
                                      const SizedBox(width: 3),
                                      Text(
                                        item.rating!.toStringAsFixed(1),
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontWeight: FontWeight.bold,
                                          fontSize: 12,
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      const Text('•', style: TextStyle(color: Colors.white38)),
                                      const SizedBox(width: 8),
                                    ],
                                    Text(
                                      item.episodesCount > 0
                                          ? '${item.episodesCount} épisodes'
                                          : 'Micro-série',
                                      style: const TextStyle(color: Colors.white70, fontSize: 12),
                                    ),
                                  ],
                                ),

                                // Synopsis court
                                if (item.synopsis.isNotEmpty) ...[
                                  const SizedBox(height: 8),
                                  Text(
                                    item.synopsis,
                                    textAlign: TextAlign.center,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      color: Colors.white.withValues(alpha: 0.8),
                                      fontSize: 12,
                                      height: 1.3,
                                    ),
                                  ),
                                ],
                                const SizedBox(height: 16),

                                // Boutons d'action : "Regarder" et "+ Ma liste"
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    // Bouton Regarder principal
                                    TouchableScale(
                                      onTap: () {
                                        if (widget.onWatch != null) {
                                          widget.onWatch!(item);
                                        } else {
                                          Navigator.push(
                                            context,
                                            MaterialPageRoute(
                                              builder: (_) => SeriesDetailScreen(
                                                seriesId: item.id,
                                                initialTitle: item.titleFr ?? item.title,
                                                initialPoster: item.posterPath,
                                              ),
                                            ),
                                          );
                                        }
                                      },
                                      child: Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
                                        decoration: BoxDecoration(
                                          color: Colors.white,
                                          borderRadius: BorderRadius.circular(6),
                                          boxShadow: [
                                            BoxShadow(
                                              color: Colors.white.withValues(alpha: 0.25),
                                              blurRadius: 10,
                                              offset: const Offset(0, 3),
                                            ),
                                          ],
                                        ),
                                        child: Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            const Icon(Icons.play_arrow, color: Colors.black, size: 24),
                                            const SizedBox(width: 6),
                                            Text(
                                              l10n.play,
                                              style: const TextStyle(
                                                color: Colors.black,
                                                fontSize: 15,
                                                fontWeight: FontWeight.bold,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 14),

                                    // Bouton "+ Ma liste"
                                    Consumer(
                                      builder: (context, ref, _) {
                                        return TouchableScale(
                                          onTap: () {
                                            // Navigation vers la page de détail où la gestion de liste/favoris est complète
                                            Navigator.push(
                                              context,
                                              MaterialPageRoute(
                                                builder: (_) => SeriesDetailScreen(
                                                  seriesId: item.id,
                                                  initialTitle: item.titleFr ?? item.title,
                                                  initialPoster: item.posterPath,
                                                ),
                                              ),
                                            );
                                          },
                                          child: Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
                                            decoration: BoxDecoration(
                                              color: Colors.white.withValues(alpha: 0.15),
                                              borderRadius: BorderRadius.circular(6),
                                              border: Border.all(
                                                color: Colors.white.withValues(alpha: 0.3),
                                                width: 1,
                                              ),
                                            ),
                                            child: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                const Icon(Icons.info_outline, color: Colors.white, size: 20),
                                                const SizedBox(width: 6),
                                                Text(
                                                  l10n.details,
                                                  style: const TextStyle(
                                                    color: Colors.white,
                                                    fontSize: 14,
                                                    fontWeight: FontWeight.w600,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        );
                                      },
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),

                // 2. Indicateurs animés en bas (Dots / barres de progression)
                Positioned(
                  bottom: 16,
                  left: 0,
                  right: 0,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(widget.items.length, (idx) {
                      final isActive = idx == _currentIndex;
                      return AnimatedContainer(
                        duration: const Duration(milliseconds: 300),
                        curve: Curves.easeOutCubic,
                        margin: const EdgeInsets.symmetric(horizontal: 3),
                        height: 5,
                        width: isActive ? 22 : 6,
                        decoration: BoxDecoration(
                          color: isActive ? AppTheme.netflixRed : Colors.white.withValues(alpha: 0.3),
                          borderRadius: BorderRadius.circular(3),
                          boxShadow: isActive
                              ? [
                                  BoxShadow(
                                    color: AppTheme.netflixRed.withValues(alpha: 0.6),
                                    blurRadius: 6,
                                  ),
                                ]
                              : null,
                        ),
                      );
                    }),
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
