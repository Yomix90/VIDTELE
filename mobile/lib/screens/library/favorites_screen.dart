import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/library_provider.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/error_state.dart';
import '../../widgets/shimmer_placeholder.dart';
import '../../widgets/touchable_scale.dart';
import '../../widgets/video_card.dart';
import '../player/reels_screen.dart';

enum FavoriteFilter { all, series, inProgress }

/// Écran « Ma Liste » / Favoris avec filtres, retour tactile et design Netflix
class FavoritesScreen extends ConsumerStatefulWidget {
  const FavoritesScreen({super.key});

  @override
  ConsumerState<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends ConsumerState<FavoritesScreen> {
  FavoriteFilter _activeFilter = FavoriteFilter.all;

  @override
  Widget build(BuildContext context) {
    final favoritesAsync = ref.watch(favoritesProvider);
    final l10n = context.l10n;

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      appBar: AppBar(
        title: Text(
          l10n.myListTitle,
          style: const TextStyle(fontWeight: FontWeight.bold, letterSpacing: 0.3),
        ),
        backgroundColor: Colors.black.withValues(alpha: 0.8),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white70),
            tooltip: l10n.refresh,
            onPressed: () {
              HapticFeedback.lightImpact();
              ref.read(favoritesProvider.notifier).fetchFavorites();
            },
          ),
        ],
      ),
      body: favoritesAsync.when(
        loading: () => GridView.builder(
          padding: const EdgeInsets.all(16),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 3,
            childAspectRatio: 0.65,
            crossAxisSpacing: 10,
            mainAxisSpacing: 12,
          ),
          itemCount: 9,
          itemBuilder: (_, __) => const ShimmerBox(borderRadius: 8),
        ),
        error: (err, _) => ErrorStateView(
          message: '${l10n.favoritesLoadError} : $err',
          retryLabel: l10n.retry,
          onRetry: () => ref.read(favoritesProvider.notifier).fetchFavorites(),
        ),
        data: (favorites) {
          if (favorites.isEmpty) {
            return EmptyStateView(
              icon: Icons.bookmark_border_rounded,
              title: l10n.myListEmptyTitle,
              subtitle: l10n.myListEmptySubtitle,
            );
          }

          // Filtrer les favoris selon l'onglet actif
          final filteredFavorites = favorites.where((video) {
            switch (_activeFilter) {
              case FavoriteFilter.all:
                return true;
              case FavoriteFilter.series:
                return video.isSeriesEpisode || video.category.toLowerCase().contains('série');
              case FavoriteFilter.inProgress:
                return video.watchProgressSeconds > 0 && !video.isCompleted;
            }
          }).toList();

          return Column(
            children: [
              // Barre de filtres (Tout, Séries, En cours)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                child: Row(
                  children: [
                    _buildFilterChip(
                      label: l10n.filterAll,
                      filter: FavoriteFilter.all,
                      count: favorites.length,
                    ),
                    const SizedBox(width: 8),
                    _buildFilterChip(
                      label: l10n.filterSeries,
                      filter: FavoriteFilter.series,
                      count: favorites.where((v) => v.isSeriesEpisode || v.category.toLowerCase().contains('série')).length,
                    ),
                    const SizedBox(width: 8),
                    _buildFilterChip(
                      label: l10n.filterInProgress,
                      filter: FavoriteFilter.inProgress,
                      count: favorites.where((v) => v.watchProgressSeconds > 0 && !v.isCompleted).length,
                    ),
                  ],
                ),
              ),

              // Grille de résultats
              Expanded(
                child: filteredFavorites.isEmpty
                    ? Center(
                        child: Text(
                          'Aucun élément dans cette section',
                          style: TextStyle(color: Colors.white.withValues(alpha: 0.5)),
                        ),
                      )
                    : RefreshIndicator(
                        color: AppTheme.netflixRed,
                        backgroundColor: AppTheme.netflixCard,
                        onRefresh: () => ref.read(favoritesProvider.notifier).fetchFavorites(),
                        child: GridView.builder(
                          padding: const EdgeInsets.all(16),
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 3,
                            childAspectRatio: 0.62,
                            crossAxisSpacing: 10,
                            mainAxisSpacing: 12,
                          ),
                          itemCount: filteredFavorites.length,
                          itemBuilder: (context, index) {
                            final video = filteredFavorites[index];
                            return Stack(
                              children: [
                                TouchableScale(
                                  onTap: () {
                                    final seriesPlaylist = (video.seriesId != null)
                                        ? filteredFavorites.where((v) => v.seriesId == video.seriesId).toList()
                                        : filteredFavorites;
                                    Navigator.push(
                                      context,
                                      MaterialPageRoute(
                                        builder: (_) => ReelsScreen(
                                          isActive: true,
                                          isStandalone: true,
                                          initialVideo: video,
                                          playlist: (video.seriesId != null && seriesPlaylist.length <= 1)
                                              ? null
                                              : seriesPlaylist,
                                          initialVideoId: video.id,
                                          seriesId: video.seriesId,
                                        ),
                                      ),
                                    );
                                  },
                                  child: VideoCard(
                                    video: video,
                                    width: double.infinity,
                                    height: double.infinity,
                                    onTap: () {
                                      final seriesPlaylist = (video.seriesId != null)
                                          ? filteredFavorites.where((v) => v.seriesId == video.seriesId).toList()
                                          : filteredFavorites;
                                      Navigator.push(
                                        context,
                                        MaterialPageRoute(
                                          builder: (_) => ReelsScreen(
                                            isActive: true,
                                            isStandalone: true,
                                            initialVideo: video,
                                            playlist: (video.seriesId != null && seriesPlaylist.length <= 1)
                                                ? null
                                                : seriesPlaylist,
                                            initialVideoId: video.id,
                                            seriesId: video.seriesId,
                                          ),
                                        ),
                                      );
                                    },
                                  ),
                                ),
                                // Bouton rapide de suppression avec croix stylisée
                                Positioned(
                                  top: 4,
                                  right: 4,
                                  child: GestureDetector(
                                    onTap: () {
                                      HapticFeedback.lightImpact();
                                      ref.read(favoritesProvider.notifier).toggleFavorite(video);
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        SnackBar(
                                          content: Text('${video.title} retiré de Ma liste'),
                                          duration: const Duration(seconds: 2),
                                          backgroundColor: AppTheme.darkSurface,
                                          action: SnackBarAction(
                                            label: 'Annuler',
                                            textColor: AppTheme.netflixRed,
                                            onPressed: () {
                                              ref.read(favoritesProvider.notifier).toggleFavorite(video);
                                            },
                                          ),
                                        ),
                                      );
                                    },
                                    child: Container(
                                      padding: const EdgeInsets.all(4),
                                      decoration: BoxDecoration(
                                        color: Colors.black.withValues(alpha: 0.75),
                                        shape: BoxShape.circle,
                                        border: Border.all(color: Colors.white24, width: 0.5),
                                      ),
                                      child: const Icon(
                                        Icons.close,
                                        color: Colors.white,
                                        size: 14,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            );
                          },
                        ),
                      ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildFilterChip({
    required String label,
    required FavoriteFilter filter,
    required int count,
  }) {
    final isSelected = _activeFilter == filter;

    return TouchableScale(
      onTap: () {
        HapticFeedback.selectionClick();
        setState(() => _activeFilter = filter);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.netflixRed : const Color(0xFF1E1E26),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? AppTheme.netflixRed : Colors.white12,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              style: TextStyle(
                color: isSelected ? Colors.white : Colors.white70,
                fontSize: 12.5,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              ),
            ),
            if (count > 0) ...[
              const SizedBox(width: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: isSelected ? Colors.white24 : Colors.white10,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '$count',
                  style: TextStyle(
                    color: isSelected ? Colors.white : Colors.white60,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
