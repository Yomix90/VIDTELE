import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants/api_constants.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/image_utils.dart';
import '../../models/series_detail_model.dart';
import '../../providers/locale_provider.dart';
import '../../providers/video_provider.dart';
import '../player/video_player_screen.dart';

/// Écran complet de détail d'une Série TV style Netflix.
/// Affiche la fiche de la série, le sélecteur de saisons, et la table complète des épisodes
/// ordonnés par numéro d'épisode avec progression de lecture (reprise) et lecture directe.
class SeriesDetailScreen extends ConsumerStatefulWidget {
  final int seriesId;
  final String? initialTitle;
  final String? initialPoster;

  const SeriesDetailScreen({
    super.key,
    required this.seriesId,
    this.initialTitle,
    this.initialPoster,
  });

  @override
  ConsumerState<SeriesDetailScreen> createState() => _SeriesDetailScreenState();
}

class _SeriesDetailScreenState extends ConsumerState<SeriesDetailScreen> {
  int _selectedSeasonIndex = 0;

  void _playEpisode(EpisodeModel episode, List<EpisodeModel> seasonEpisodes) {
    if (episode.video == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cette vidéo n\'est pas encore disponible sur le serveur.'),
          backgroundColor: Colors.redAccent,
        ),
      );
      return;
    }

    // Préparer la playlist dans l'ordre strict des épisodes de la saison
    final playlist = seasonEpisodes
        .where((e) => e.video != null)
        .map((e) => e.video!)
        .toList();

    final initialIndex = playlist.indexWhere((v) => v.id == episode.video!.id);

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => VideoPlayerScreen(
          video: episode.video!,
          playlist: playlist,
          initialIndex: initialIndex >= 0 ? initialIndex : 0,
        ),
      ),
    ).then((_) {
      // Recharger les données de la série au retour pour rafraîchir l'historique et les progressions
      ref.invalidate(seriesDetailProvider(widget.seriesId));
      ref.invalidate(videoListProvider);
    });
  }

  @override
  Widget build(BuildContext context) {
    final seriesAsync = ref.watch(seriesDetailProvider(widget.seriesId));
    final currentLocale = ref.watch(localeProvider);
    final langCode = currentLocale.languageCode;
    final l10n = context.l10n;

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      body: seriesAsync.when(
        loading: () => const Center(
          child: CircularProgressIndicator(color: AppTheme.netflixRed),
        ),
        error: (err, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
              const SizedBox(height: 12),
              Text(
                l10n.catalogLoadError,
                style: const TextStyle(color: Colors.white70),
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => ref.invalidate(seriesDetailProvider(widget.seriesId)),
                child: Text(l10n.retry),
              ),
            ],
          ),
        ),
        data: (series) {
          if (series == null) {
            return const Center(
              child: Text('Série introuvable', style: TextStyle(color: Colors.white70)),
            );
          }

          final title = series.getLocalizedTitle(langCode);
          final synopsis = series.getLocalizedSynopsis(langCode);
          final seasons = series.seasons;
          final currentSeason = seasons.isNotEmpty && _selectedSeasonIndex < seasons.length
              ? seasons[_selectedSeasonIndex]
              : null;

          // Déterminer le prochain épisode à regarder (reprise de lecture)
          EpisodeModel? resumeEpisode;
          if (series.lastWatchedEpisodeId != null) {
            for (final s in seasons) {
              final found = s.episodes.where((e) => e.id == series.lastWatchedEpisodeId).firstOrNull;
              if (found != null) {
                resumeEpisode = found;
                break;
              }
            }
          }
          if (resumeEpisode == null && seasons.isNotEmpty && seasons.first.episodes.isNotEmpty) {
            resumeEpisode = seasons.first.episodes.first;
          }

          return FutureBuilder<String>(
            future: storageService.getServerUrl(),
            builder: (context, snapshot) {
              final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;
              final bannerUrl = ImageUtils.resolveUrl(series.bannerPath ?? series.posterPath, baseUrl);

              return CustomScrollView(
                slivers: [
                  // 1. Grande Bannière Hero avec AppBar rétractable
                  SliverAppBar(
                    expandedHeight: 280,
                    pinned: true,
                    backgroundColor: Colors.black,
                    leading: IconButton(
                      icon: const Icon(Icons.arrow_back, color: Colors.white),
                      onPressed: () => Navigator.pop(context),
                    ),
                    flexibleSpace: FlexibleSpaceBar(
                      background: Stack(
                        fit: StackFit.expand,
                        children: [
                          if (bannerUrl != null && bannerUrl.isNotEmpty)
                            CachedNetworkImage(
                              imageUrl: bannerUrl,
                              fit: BoxFit.cover,
                              placeholder: (context, url) => Container(color: AppTheme.netflixDarkGray),
                              errorWidget: (context, url, error) => Container(color: AppTheme.netflixDarkGray),
                            )
                          else
                            Container(color: AppTheme.netflixDarkGray),
                          // Dégradé sombre
                          Container(
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                begin: Alignment.topCenter,
                                end: Alignment.bottomCenter,
                                colors: [
                                  Colors.black.withValues(alpha: 0.3),
                                  Colors.transparent,
                                  AppTheme.netflixBlack.withValues(alpha: 0.8),
                                  AppTheme.netflixBlack,
                                ],
                                stops: const [0.0, 0.4, 0.8, 1.0],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  // 2. Informations de la Série
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Titre principal
                          Text(
                            title,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.5,
                            ),
                          ),
                          const SizedBox(height: 8),

                          // Badges d'information : Année, Note, Saisons, Statut
                          Wrap(
                            spacing: 8,
                            runSpacing: 6,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              if (series.yearStart != null)
                                Text(
                                  '${series.yearStart}',
                                  style: const TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.w600),
                                ),
                              if (series.rating != null && series.rating! > 0)
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: Colors.amber.shade700,
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      const Icon(Icons.star, size: 12, color: Colors.black),
                                      const SizedBox(width: 3),
                                      Text(
                                        series.rating!.toStringAsFixed(1),
                                        style: const TextStyle(color: Colors.black, fontSize: 11, fontWeight: FontWeight.bold),
                                      ),
                                    ],
                                  ),
                                ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.white12,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  '${series.seasonsCount} ${langCode == 'ar' ? 'مواسم' : 'Saison(s)'}',
                                  style: const TextStyle(color: Colors.white70, fontSize: 11),
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: AppTheme.netflixRed.withValues(alpha: 0.2),
                                  border: Border.all(color: AppTheme.netflixRed.withValues(alpha: 0.5)),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  '${series.episodesCount} ${langCode == 'ar' ? 'حلقات' : 'Épisodes'}',
                                  style: const TextStyle(color: AppTheme.netflixRed, fontSize: 11, fontWeight: FontWeight.bold),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),

                          // Bouton de reprise directe
                          if (resumeEpisode != null && resumeEpisode.video != null)
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton.icon(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppTheme.netflixRed,
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(vertical: 13),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                ),
                                icon: const Icon(Icons.play_arrow, size: 24),
                                label: Text(
                                  resumeEpisode.watchProgressSeconds > 0 && !resumeEpisode.isCompleted
                                      ? (langCode == 'ar'
                                          ? 'متابعة المشاهدة (حلقة ${resumeEpisode.number})'
                                          : 'Reprendre la lecture (Ép. ${resumeEpisode.number})')
                                      : (langCode == 'ar'
                                          ? 'بدء المشاهدة (الحلقة ${resumeEpisode.number})'
                                          : 'Regarder l\'épisode ${resumeEpisode.number}'),
                                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                                ),
                                onPressed: () {
                                  final targetSeason = seasons.firstWhere(
                                    (s) => s.id == resumeEpisode!.seasonId,
                                    orElse: () => seasons.first,
                                  );
                                  _playEpisode(resumeEpisode!, targetSeason.episodes);
                                },
                              ),
                            ),
                          const SizedBox(height: 16),

                          // Synopsis
                          if (synopsis != null && synopsis.isNotEmpty) ...[
                            Text(
                              synopsis,
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 13.5,
                                height: 1.45,
                              ),
                            ),
                            const SizedBox(height: 20),
                          ],

                          const Divider(color: Colors.white12, height: 1),
                          const SizedBox(height: 16),

                          // 3. Sélecteur d'onglets de saisons
                          if (seasons.length > 1)
                            SingleChildScrollView(
                              scrollDirection: Axis.horizontal,
                              child: Row(
                                children: List.generate(seasons.length, (idx) {
                                  final s = seasons[idx];
                                  final isSelected = idx == _selectedSeasonIndex;
                                  return Padding(
                                    padding: const EdgeInsets.only(right: 8),
                                    child: ChoiceChip(
                                      label: Text(s.getLocalizedTitle(langCode)),
                                      selected: isSelected,
                                      selectedColor: AppTheme.netflixRed,
                                      backgroundColor: AppTheme.netflixDarkGray,
                                      labelStyle: TextStyle(
                                        color: isSelected ? Colors.white : Colors.white70,
                                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                      ),
                                      onSelected: (val) {
                                        if (val) setState(() => _selectedSeasonIndex = idx);
                                      },
                                    ),
                                  );
                                }),
                              ),
                            )
                          else if (seasons.isNotEmpty)
                            Text(
                              seasons.first.getLocalizedTitle(langCode),
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 17,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          const SizedBox(height: 14),
                        ],
                      ),
                    ),
                  ),

                  // 4. Table / Liste des Épisodes de la saison sélectionnée
                  if (currentSeason != null && currentSeason.episodes.isNotEmpty)
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      sliver: SliverList(
                        delegate: SliverChildBuilderDelegate(
                          (context, index) {
                            final ep = currentSeason.episodes[index];
                            final epTitle = ep.getLocalizedTitle(langCode);
                            final epSynopsis = ep.getLocalizedSynopsis(langCode);
                            final epThumbUrl = ImageUtils.resolveUrl(
                              ep.thumbnailPath ?? series.posterPath,
                              baseUrl,
                            );

                            return InkWell(
                              borderRadius: BorderRadius.circular(8),
                              onTap: () => _playEpisode(ep, currentSeason.episodes),
                              child: Container(
                                margin: const EdgeInsets.only(bottom: 14),
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: AppTheme.netflixDarkGray.withValues(alpha: 0.4),
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(
                                    color: ep.watchProgressSeconds > 0
                                        ? AppTheme.netflixRed.withValues(alpha: 0.3)
                                        : Colors.white.withValues(alpha: 0.05),
                                  ),
                                ),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    // Miniature de l'épisode avec durée et barre de progression
                                    Stack(
                                      children: [
                                        ClipRRect(
                                          borderRadius: BorderRadius.circular(6),
                                          child: SizedBox(
                                            width: 120,
                                            height: 72,
                                            child: (epThumbUrl != null && epThumbUrl.isNotEmpty)
                                                ? CachedNetworkImage(
                                                    imageUrl: epThumbUrl,
                                                    fit: BoxFit.cover,
                                                    placeholder: (context, url) => Container(color: Colors.white10),
                                                    errorWidget: (context, url, error) => Container(
                                                      color: Colors.white10,
                                                      child: const Icon(Icons.movie, color: Colors.white24),
                                                    ),
                                                  )
                                                : Container(
                                                    color: Colors.white10,
                                                    child: const Icon(Icons.movie, color: Colors.white24),
                                                  ),
                                          ),
                                        ),
                                        // Icône Play au centre
                                        Positioned.fill(
                                          child: Center(
                                            child: Container(
                                              padding: const EdgeInsets.all(6),
                                              decoration: BoxDecoration(
                                                color: Colors.black.withValues(alpha: 0.6),
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
                                        // Badge Durée
                                        Positioned(
                                          bottom: 4,
                                          right: 4,
                                          child: Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                                            decoration: BoxDecoration(
                                              color: Colors.black.withValues(alpha: 0.8),
                                              borderRadius: BorderRadius.circular(3),
                                            ),
                                            child: Text(
                                              ep.formattedDuration,
                                              style: const TextStyle(color: Colors.white, fontSize: 9.5),
                                            ),
                                          ),
                                        ),
                                        // Barre de progression rouge Netflix en bas de la miniature
                                        if (ep.watchProgressSeconds > 0)
                                          Positioned(
                                            left: 0,
                                            right: 0,
                                            bottom: 0,
                                            child: ClipRRect(
                                              borderRadius: const BorderRadius.vertical(bottom: Radius.circular(6)),
                                              child: LinearProgressIndicator(
                                                value: ep.progressFraction,
                                                backgroundColor: Colors.white24,
                                                valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.netflixRed),
                                                minHeight: 3,
                                              ),
                                            ),
                                          ),
                                      ],
                                    ),
                                    const SizedBox(width: 12),

                                    // Détails de l'épisode
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            children: [
                                              Text(
                                                '${ep.number}. ',
                                                style: const TextStyle(
                                                  color: AppTheme.netflixRed,
                                                  fontWeight: FontWeight.bold,
                                                  fontSize: 14,
                                                ),
                                              ),
                                              Expanded(
                                                child: Text(
                                                  epTitle,
                                                  maxLines: 1,
                                                  overflow: TextOverflow.ellipsis,
                                                  style: const TextStyle(
                                                    color: Colors.white,
                                                    fontWeight: FontWeight.w600,
                                                    fontSize: 14,
                                                  ),
                                                ),
                                              ),
                                              if (ep.isCompleted)
                                                const Padding(
                                                  padding: EdgeInsets.only(left: 4),
                                                  child: Icon(Icons.check_circle, color: Colors.greenAccent, size: 16),
                                                ),
                                            ],
                                          ),
                                          const SizedBox(height: 4),
                                          if (epSynopsis != null && epSynopsis.isNotEmpty)
                                            Text(
                                              epSynopsis,
                                              maxLines: 2,
                                              overflow: TextOverflow.ellipsis,
                                              style: const TextStyle(
                                                color: Colors.white54,
                                                fontSize: 12,
                                                height: 1.3,
                                              ),
                                            )
                                          else
                                            Text(
                                              'Épisode ${ep.number} · Saison ${currentSeason.number}',
                                              style: const TextStyle(
                                                color: Colors.white38,
                                                fontSize: 11,
                                              ),
                                            ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            );
                          },
                          childCount: currentSeason.episodes.length,
                        ),
                      ),
                    )
                  else
                    const SliverToBoxAdapter(
                      child: Padding(
                        padding: EdgeInsets.all(32),
                        child: Center(
                          child: Text(
                            'Aucun épisode disponible pour cette saison.',
                            style: TextStyle(color: Colors.white54),
                          ),
                        ),
                      ),
                    ),

                  const SliverToBoxAdapter(child: SizedBox(height: 40)),
                ],
              );
            },
          );
        },
      ),
    );
  }
}
