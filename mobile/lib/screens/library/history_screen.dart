import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../core/constants/api_constants.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/library_provider.dart';
import '../player/video_player_screen.dart';

/// Écran Historique de lecture avec état d'avancement et reprise directe (support trilingue FR / EN / AR)
class HistoryScreen extends ConsumerWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyAsync = ref.watch(historyProvider);
    final l10n = context.l10n;

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      appBar: AppBar(
        title: Text(l10n.historyTitle),
        backgroundColor: Colors.black.withValues(alpha: 0.8),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: l10n.refresh,
            onPressed: () => ref.read(historyProvider.notifier).fetchHistory(),
          ),
        ],
      ),
      body: historyAsync.when(
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
                  'Erreur : $err',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white70),
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () => ref.read(historyProvider.notifier).fetchHistory(),
                  child: Text(l10n.retry),
                ),
              ],
            ),
          ),
        ),
        data: (items) {
          if (items.isEmpty) {
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
                        Icons.history_rounded,
                        size: 64,
                        color: Colors.white38,
                      ),
                    ),
                    const SizedBox(height: 24),
                    Text(
                      l10n.historyEmptyTitle,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      l10n.historyEmptySubtitle,
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
            onRefresh: () => ref.read(historyProvider.notifier).fetchHistory(),
            child: FutureBuilder<String>(
              future: storageService.getServerUrl(),
              builder: (context, snapshot) {
                final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;

                return ListView.separated(
                  padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                  itemCount: items.length,
                  separatorBuilder: (context, index) => const Divider(
                    color: Colors.white12,
                    height: 24,
                  ),
                  itemBuilder: (context, index) {
                    final item = items[index];
                    final video = item.video;
                    final thumbUrl = video.thumbnailPath != null
                        ? '$baseUrl${video.thumbnailPath}'
                        : null;

                    return InkWell(
                      onTap: () {
                        // Passer la vidéo avec la position de reprise
                        final resumingVideo = video.copyWith(
                          watchProgressSeconds: item.lastPositionSeconds,
                          isCompleted: item.isCompleted,
                        );
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => VideoPlayerScreen(video: resumingVideo),
                          ),
                        );
                      },
                      borderRadius: BorderRadius.circular(8),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Miniature avec barre de progression rouge
                            ClipRRect(
                              borderRadius: BorderRadius.circular(6),
                              child: Stack(
                                children: [
                                  SizedBox(
                                    width: 120,
                                    height: 75,
                                    child: thumbUrl != null
                                        ? CachedNetworkImage(
                                            imageUrl: thumbUrl,
                                            fit: BoxFit.cover,
                                            placeholder: (context, url) => Container(
                                              color: AppTheme.netflixCard,
                                              child: const Center(
                                                child: CircularProgressIndicator(
                                                  strokeWidth: 2,
                                                  color: AppTheme.netflixRed,
                                                ),
                                              ),
                                            ),
                                            errorWidget: (context, url, error) => Container(
                                              color: AppTheme.netflixCard,
                                              child: const Icon(Icons.movie, color: Colors.white24),
                                            ),
                                          )
                                        : Container(
                                            color: AppTheme.netflixCard,
                                            child: const Icon(Icons.movie, color: Colors.white24),
                                          ),
                                  ),
                                  // Barre rouge de progression en bas
                                  Positioned(
                                    bottom: 0,
                                    left: 0,
                                    right: 0,
                                    child: LinearProgressIndicator(
                                      value: item.progressFraction,
                                      minHeight: 4,
                                      backgroundColor: Colors.white24,
                                      valueColor: const AlwaysStoppedAnimation<Color>(
                                        AppTheme.netflixRed,
                                      ),
                                    ),
                                  ),
                                  // Icône play au centre
                                  Positioned.fill(
                                    child: Center(
                                      child: Container(
                                        padding: const EdgeInsets.all(6),
                                        decoration: BoxDecoration(
                                          color: Colors.black.withValues(alpha: 0.5),
                                          shape: BoxShape.circle,
                                        ),
                                        child: const Icon(
                                          Icons.play_arrow,
                                          color: Colors.white,
                                          size: 20,
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 14),

                            // Titre, catégorie, et statut
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    video.title,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 15,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Row(
                                    children: [
                                      Container(
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 6,
                                          vertical: 2,
                                        ),
                                        decoration: BoxDecoration(
                                          color: AppTheme.netflixRed.withValues(alpha: 0.8),
                                          borderRadius: BorderRadius.circular(3),
                                        ),
                                        child: Text(
                                          '#${video.category}',
                                          style: const TextStyle(
                                            color: Colors.white,
                                            fontSize: 10,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Text(
                                        item.isCompleted
                                            ? l10n.watchedBadge
                                            : l10n.percentCompleted((item.progressFraction * 100).toInt()),
                                        style: TextStyle(
                                          color: item.isCompleted
                                              ? Colors.greenAccent
                                              : Colors.white54,
                                          fontSize: 12,
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          );
        },
      ),
    );
  }
}
