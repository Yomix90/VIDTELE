import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/library_provider.dart';
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
        loading: () => const Center(
          child: CircularProgressIndicator(color: AppTheme.netflixRed),
        ),
        error: (err, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
                const SizedBox(height: 12),
                Text(
                  '${l10n.favoritesLoadError} : $err',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white70),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () => ref.read(favoritesProvider.notifier).fetchFavorites(),
                  child: Text(l10n.retry),
                ),
              ],
            ),
          ),
        ),
        data: (favorites) {
          if (favorites.isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 32.0),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(24),
                      decoration: const BoxDecoration(
                        color: AppTheme.netflixCard,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.bookmark_border_rounded,
                        size: 64,
                        color: Colors.white38,
                      ),
                    ),
                    const SizedBox(height: 24),
                    Text(
                      l10n.myListEmptyTitle,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      l10n.myListEmptySubtitle,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white54, fontSize: 14),
                    ),
                  ],
                ),
              ),
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
