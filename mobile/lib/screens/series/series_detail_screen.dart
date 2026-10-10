import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/constants/api_constants.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/image_utils.dart';
import '../../models/series_detail_model.dart';
import '../../providers/locale_provider.dart';
import '../../providers/video_provider.dart';
import '../../widgets/shimmer_placeholder.dart';
import '../../widgets/touchable_scale.dart';
import '../player/reels_screen.dart';

/// Écran complet de détail d'une Série TV au standard Netflix / DramaBox.
/// Comprend :
/// - Grande bannière Hero avec animation Hero, dégradé cinématique et retour tactile
/// - Métadonnées enrichies : Note IMDb/TMDB, année, nombre de saisons, total épisodes, tags de genres
/// - Synopsis repliable avec bouton Plus / Moins animé
/// - Boutons d'action : Regarder l'épisode en cours, Binge vertical style TikTok (Reels), Ma liste
/// - Onglets de saisons et table d'épisodes avec miniatures 16:9, durée et barre de progression rouge
/// - Section de recommandations « Séries similaires »
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
  bool _isSynopsisExpanded = false;
  bool? _localIsFavorite;

  void _playEpisode(EpisodeModel episode, List<EpisodeModel> seasonEpisodes) {
    if (episode.video == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cet épisode n\'est pas encore disponible sur le serveur.'),
          backgroundColor: Colors.redAccent,
        ),
      );
      return;
    }

    final playlist = seasonEpisodes
        .where((e) => e.video != null)
        .map((e) => e.video!)
        .toList();

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReelsScreen(
          seriesId: widget.seriesId,
          initialVideoId: episode.video!.id,
          initialVideo: episode.video,
          playlist: playlist,
          isActive: true,
          isStandalone: true,
        ),
      ),
    ).then((_) {
      ref.invalidate(seriesDetailProvider(widget.seriesId));
      ref.invalidate(videoListProvider);
    });
  }

  void _playInReels(BuildContext context) {
    HapticFeedback.lightImpact();
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReelsScreen(
          seriesId: widget.seriesId,
          isActive: true,
          isStandalone: true,
        ),
      ),
    ).then((_) {
      ref.invalidate(seriesDetailProvider(widget.seriesId));
    });
  }

  Future<void> _toggleFavorite(bool currentStatus, AppLocalizations l10n) async {
    HapticFeedback.mediumImpact();
    final newStatus = !currentStatus;
    setState(() => _localIsFavorite = newStatus);

    try {
      final res = await apiClient.dio.post(ApiConstants.seriesFavorite(widget.seriesId));
      if (res.statusCode == 200 && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(newStatus ? l10n.addedToMyList : l10n.removedFromMyList),
            duration: const Duration(seconds: 2),
            backgroundColor: AppTheme.darkSurface,
          ),
        );
      }
    } catch (_) {
      // Annuler en cas d'échec réseau
      if (mounted) {
        setState(() => _localIsFavorite = currentStatus);
      }
    }
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
        loading: () => _buildShimmerLoading(),
        error: (err, _) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
                const SizedBox(height: 12),
                Text(
                  l10n.catalogLoadError,
                  style: const TextStyle(color: Colors.white70),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.netflixRed,
                    foregroundColor: Colors.white,
                  ),
                  onPressed: () => ref.invalidate(seriesDetailProvider(widget.seriesId)),
                  child: Text(l10n.retry),
                ),
              ],
            ),
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

          final isFavorite = _localIsFavorite ?? series.isFavorite;

          // Déterminer le prochain épisode à regarder (reprise ou premier épisode)
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
                    expandedHeight: 320,
                    pinned: true,
                    backgroundColor: AppTheme.netflixBlack,
                    leading: Padding(
                      padding: const EdgeInsets.all(8),
                      child: CircleAvatar(
                        backgroundColor: Colors.black54,
                        child: IconButton(
                          icon: const Icon(Icons.arrow_back, color: Colors.white, size: 20),
                          onPressed: () => Navigator.pop(context),
                        ),
                      ),
                    ),
                    flexibleSpace: FlexibleSpaceBar(
                      background: Stack(
                        fit: StackFit.expand,
                        children: [
                          if (bannerUrl != null && bannerUrl.isNotEmpty)
                            Hero(
                              tag: 'series_poster_${series.id}',
                              child: CachedNetworkImage(
                                imageUrl: bannerUrl,
                                fit: BoxFit.cover,
                                placeholder: (context, url) => Container(color: AppTheme.netflixDarkGray),
                                errorWidget: (context, url, error) => Container(color: AppTheme.netflixDarkGray),
                              ),
                            )
                          else
                            Container(color: AppTheme.netflixDarkGray),

                          // Dégradé sombre cinématique multicouches
                          Container(
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                begin: Alignment.topCenter,
                                end: Alignment.bottomCenter,
                                colors: [
                                  Colors.black.withValues(alpha: 0.4),
                                  Colors.transparent,
                                  AppTheme.netflixBlack.withValues(alpha: 0.8),
                                  AppTheme.netflixBlack,
                                ],
                                stops: const [0.0, 0.45, 0.82, 1.0],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  // 2. Fiche d'informations et actions
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Titre de la série
                          Text(
                            title,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 26,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.3,
                            ),
                          ),
                          const SizedBox(height: 8),

                          // Badges d'information : Note, Année, Saisons, Épisodes
                          Wrap(
                            spacing: 8,
                            runSpacing: 6,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              if (series.rating != null && series.rating! > 0)
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2.5),
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
                                        style: const TextStyle(
                                          color: Colors.black,
                                          fontSize: 11.5,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              if (series.yearStart != null)
                                Text(
                                  '${series.yearStart}',
                                  style: const TextStyle(
                                    color: Colors.white70,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
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
                                  color: AppTheme.netflixRed.withValues(alpha: 0.15),
                                  border: Border.all(color: AppTheme.netflixRed.withValues(alpha: 0.4)),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  '${series.episodesCount} ${langCode == 'ar' ? 'حلقات' : 'Épisodes'}',
                                  style: const TextStyle(
                                    color: AppTheme.netflixRed,
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),

                          // Tags de genres
                          if (series.genres.isNotEmpty)
                            Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: series.genres.map((g) {
                                return Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFF1E1E26),
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(color: Colors.white10),
                                  ),
                                  child: Text(
                                    g,
                                    style: const TextStyle(color: Colors.white70, fontSize: 11),
                                  ),
                                );
                              }).toList(),
                            ),
                          const SizedBox(height: 16),

                          // Bouton 1 : Regarder / Reprendre
                          if (resumeEpisode != null && resumeEpisode.video != null) ...[
                            TouchableScale(
                              onTap: () {
                                final targetSeason = seasons.firstWhere(
                                  (s) => s.id == resumeEpisode!.seasonId,
                                  orElse: () => seasons.first,
                                );
                                _playEpisode(resumeEpisode!, targetSeason.episodes);
                              },
                              child: Container(
                                width: double.infinity,
                                padding: const EdgeInsets.symmetric(vertical: 14),
                                decoration: BoxDecoration(
                                  color: AppTheme.netflixRed,
                                  borderRadius: BorderRadius.circular(8),
                                  boxShadow: [
                                    BoxShadow(
                                      color: AppTheme.netflixRed.withValues(alpha: 0.4),
                                      blurRadius: 12,
                                      offset: const Offset(0, 4),
                                    ),
                                  ],
                                ),
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    const Icon(Icons.play_arrow, color: Colors.white, size: 24),
                                    const SizedBox(width: 8),
                                    Text(
                                      resumeEpisode.watchProgressSeconds > 0 && !resumeEpisode.isCompleted
                                          ? (langCode == 'ar'
                                              ? 'متابعة المشاهدة (حلقة ${resumeEpisode.number})'
                                              : 'Reprendre la lecture (Ép. ${resumeEpisode.number})')
                                          : (langCode == 'ar'
                                              ? 'بدء المشاهدة (الحلقة ${resumeEpisode.number})'
                                              : 'Regarder l\'épisode ${resumeEpisode.number}'),
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            const SizedBox(height: 10),
                          ],

                          // Bouton 2 : Binge vertical style TikTok (Reels)
                          TouchableScale(
                            onTap: () => _playInReels(context),
                            child: Container(
                              width: double.infinity,
                              padding: const EdgeInsets.symmetric(vertical: 12),
                              decoration: BoxDecoration(
                                color: const Color(0xFF1E1E26),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: Colors.white12),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  const Icon(Icons.stay_current_portrait_rounded, color: Colors.white, size: 20),
                                  const SizedBox(width: 8),
                                  Text(
                                    l10n.watchVertical,
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 14,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 14),

                          // Action secondaire : Ma Liste
                          Center(
                            child: TouchableScale(
                              onTap: () => _toggleFavorite(isFavorite, l10n),
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    isFavorite ? Icons.check : Icons.add,
                                    color: isFavorite ? AppTheme.netflixRed : Colors.white,
                                    size: 26,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    l10n.myListTitle,
                                    style: TextStyle(
                                      color: isFavorite ? AppTheme.netflixRed : Colors.white70,
                                      fontSize: 12,
                                      fontWeight: isFavorite ? FontWeight.bold : FontWeight.normal,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 18),

                          // Synopsis repliable
                          if (synopsis != null && synopsis.isNotEmpty) ...[
                            AnimatedCrossFade(
                              firstChild: Text(
                                synopsis,
                                maxLines: 3,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  color: Colors.white70,
                                  fontSize: 13.5,
                                  height: 1.45,
                                ),
                              ),
                              secondChild: Text(
                                synopsis,
                                style: const TextStyle(
                                  color: Colors.white70,
                                  fontSize: 13.5,
                                  height: 1.45,
                                ),
                              ),
                              crossFadeState: _isSynopsisExpanded
                                  ? CrossFadeState.showSecond
                                  : CrossFadeState.showFirst,
                              duration: const Duration(milliseconds: 250),
                            ),
                            const SizedBox(height: 4),
                            GestureDetector(
                              onTap: () {
                                HapticFeedback.selectionClick();
                                setState(() => _isSynopsisExpanded = !_isSynopsisExpanded);
                              },
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    _isSynopsisExpanded ? l10n.collapse : l10n.expand,
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 12.5,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  Icon(
                                    _isSynopsisExpanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
                                    color: Colors.white,
                                    size: 16,
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 16),
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
                          const SizedBox(height: 12),
                        ],
                      ),
                    ),
                  ),

                  // 4. Liste des Épisodes de la saison active
                  if (currentSeason != null && currentSeason.episodes.isNotEmpty)
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
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

                            return TouchableScale(
                              onTap: () => _playEpisode(ep, currentSeason.episodes),
                              child: Container(
                                margin: const EdgeInsets.only(bottom: 12),
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF141419),
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
                                    // Miniature 16:9 avec barre de progression
                                    Stack(
                                      children: [
                                        ClipRRect(
                                          borderRadius: BorderRadius.circular(6),
                                          child: SizedBox(
                                            width: 124,
                                            height: 74,
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
                                        Positioned.fill(
                                          child: Center(
                                            child: Container(
                                              padding: const EdgeInsets.all(5),
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

                                    // Métadonnées de l'épisode
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

                  // 5. Section « Séries similaires »
                  if (series.similarSeries.isNotEmpty) ...[
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(16, 24, 16, 12),
                        child: Text(
                          l10n.similarSeries,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: SizedBox(
                        height: 190,
                        child: ListView.builder(
                          scrollDirection: Axis.horizontal,
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: series.similarSeries.length,
                          itemBuilder: (context, index) {
                            final sim = series.similarSeries[index];
                            final simTitle = sim.getLocalizedTitle(langCode);
                            final simPosterUrl = ImageUtils.resolveUrl(sim.posterPath, baseUrl);

                            return Container(
                              width: 115,
                              margin: const EdgeInsets.only(right: 12),
                              child: TouchableScale(
                                onTap: () {
                                  Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) => SeriesDetailScreen(
                                        seriesId: sim.id,
                                        initialTitle: simTitle,
                                        initialPoster: sim.posterPath,
                                      ),
                                    ),
                                  );
                                },
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    ClipRRect(
                                      borderRadius: BorderRadius.circular(8),
                                      child: AspectRatio(
                                        aspectRatio: 2 / 3,
                                        child: (simPosterUrl != null && simPosterUrl.isNotEmpty)
                                            ? CachedNetworkImage(
                                                imageUrl: simPosterUrl,
                                                fit: BoxFit.cover,
                                                placeholder: (context, url) => Container(color: AppTheme.netflixDarkGray),
                                                errorWidget: (context, url, error) => Container(
                                                  color: AppTheme.netflixDarkGray,
                                                  child: const Icon(Icons.movie, color: Colors.white24),
                                                ),
                                              )
                                            : Container(
                                                color: AppTheme.netflixDarkGray,
                                                child: const Icon(Icons.movie, color: Colors.white24),
                                              ),
                                      ),
                                    ),
                                    const SizedBox(height: 6),
                                    Text(
                                      simTitle,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 12.5,
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                    if (sim.rating != null && sim.rating! > 0)
                                      Row(
                                        children: [
                                          const Icon(Icons.star, size: 10, color: Colors.amber),
                                          const SizedBox(width: 3),
                                          Text(
                                            sim.rating!.toStringAsFixed(1),
                                            style: const TextStyle(color: Colors.white54, fontSize: 11),
                                          ),
                                        ],
                                      ),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                  ],

                  const SliverToBoxAdapter(child: SizedBox(height: 40)),
                ],
              );
            },
          );
        },
      ),
    );
  }

  Widget _buildShimmerLoading() {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const ShimmerBox(width: double.infinity, height: 320, borderRadius: 0),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const ShimmerBox(width: 200, height: 26),
                const SizedBox(height: 12),
                const Row(
                  children: [
                    ShimmerBox(width: 40, height: 18),
                    SizedBox(width: 8),
                    ShimmerBox(width: 60, height: 18),
                    SizedBox(width: 8),
                    ShimmerBox(width: 70, height: 18),
                  ],
                ),
                const SizedBox(height: 16),
                const ShimmerBox(width: double.infinity, height: 48),
                const SizedBox(height: 12),
                const ShimmerBox(width: double.infinity, height: 40),
                const SizedBox(height: 24),
                const ShimmerBox(width: double.infinity, height: 14),
                const SizedBox(height: 6),
                const ShimmerBox(width: 250, height: 14),
                const SizedBox(height: 24),
                ...List.generate(
                  3,
                  (_) => const Padding(
                    padding: EdgeInsets.only(bottom: 12),
                    child: ShimmerBox(width: double.infinity, height: 80),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
