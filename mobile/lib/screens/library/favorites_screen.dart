import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/library_provider.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/error_state.dart';
import '../../widgets/shimmer_placeholder.dart';
import '../../widgets/video_card.dart';
import '../player/video_player_screen.dart';

/// Écran "Ma Liste" / Favoris au design Netflix avec support trilingue FR / EN / AR
class FavoritesScreen extends ConsumerWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final favoritesAsync = ref.watch(favoritesProvider);
    final l10n = context.l10n;

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      appBar: AppBar(
        title: Text(l10n.myListTitle),
        backgroundColor: Colors.black.withValues(alpha: 0.8),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: l10n.refresh,
            onPressed: () => ref.read(favoritesProvider.notifier).fetchFavorites(),
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

          return RefreshIndicator(
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
              itemCount: favorites.length,
              itemBuilder: (context, index) {
                final video = favorites[index];
                return Stack(
                  children: [
                    VideoCard(
                      video: video,
                      width: double.infinity,
                      height: double.infinity,
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => VideoPlayerScreen(video: video),
                          ),
                        );
                      },
                    ),
                    // Bouton rapide de suppression
                    Positioned(
                      top: 4,
                      right: 16,
                      child: GestureDetector(
                        onTap: () {
                          ref.read(favoritesProvider.notifier).toggleFavorite(video);
                        },
                        child: Container(
                          padding: const EdgeInsets.all(4),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.7),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.close,
                            color: Colors.white,
                            size: 16,
                          ),
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          );
        },
      ),
    );
  }
}
