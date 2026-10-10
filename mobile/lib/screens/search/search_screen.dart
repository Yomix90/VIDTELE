import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants/api_constants.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/image_utils.dart';
import '../../models/series_detail_model.dart';
import '../../models/video_model.dart';
import '../../providers/locale_provider.dart';
import '../../providers/video_provider.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/shimmer_placeholder.dart';
import '../../widgets/touchable_scale.dart';
import '../../widgets/video_card.dart';
import '../player/reels_screen.dart';
import '../series/series_detail_screen.dart';

/// Écran dédié à la recherche dynamique, exploration par catégorie et suggestions
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final TextEditingController _controller = TextEditingController();
  String _selectedCategory = '';

  static const List<String> _popularSuggestions = [
    'Drame',
    'Action',
    'Micro-série',
    'Romance',
    'Thriller',
    'Comédie',
  ];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onVideoSelected(VideoModel video, [List<VideoModel>? playlist]) {
    final seriesPlaylist = (video.seriesId != null && playlist != null)
        ? playlist.where((v) => v.seriesId == video.seriesId).toList()
        : playlist;

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReelsScreen(
          isActive: true,
          isStandalone: true,
          initialVideo: video,
          playlist: (video.seriesId != null && (seriesPlaylist == null || seriesPlaylist.length <= 1))
              ? null
              : seriesPlaylist,
          initialVideoId: video.id,
          seriesId: video.seriesId,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final allVideosAsync = ref.watch(videoListProvider);
    final categoriesAsync = ref.watch(categoriesProvider);
    final seriesListAsync = ref.watch(seriesListProvider);
    final currentLocale = ref.watch(localeProvider);
    final langCode = currentLocale.languageCode;
    final query = _controller.text.trim().toLowerCase();

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      body: SafeArea(
        child: Column(
          children: [
            // 1. Barre de recherche moderne avec retour haptique
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Container(
                decoration: BoxDecoration(
                  color: const Color(0xFF16161E),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
                ),
                child: TextField(
                  controller: _controller,
                  style: const TextStyle(color: Colors.white, fontSize: 15),
                  decoration: InputDecoration(
                    hintText: l10n.searchPlaceholder,
                    hintStyle: const TextStyle(color: Colors.white38, fontSize: 14),
                    prefixIcon: const Icon(Icons.search, color: Colors.white54, size: 22),
                    suffixIcon: _controller.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.close, color: Colors.white54, size: 20),
                            onPressed: () {
                              HapticFeedback.lightImpact();
                              _controller.clear();
                              setState(() {});
                            },
                          )
                        : null,
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                  ),
                  onChanged: (_) => setState(() {}),
                ),
              ),
            ),

            // 2. Filtres par catégorie
            categoriesAsync.when(
              data: (categories) {
                if (categories.isEmpty) return const SizedBox.shrink();
                return SizedBox(
                  height: 44,
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemCount: categories.length + 1,
                    itemBuilder: (context, index) {
                      final isAll = index == 0;
                      final catName = isAll ? '' : categories[index - 1].name;
                      final isSelected = _selectedCategory == catName;

                      return Padding(
                        padding: const EdgeInsets.only(right: 8, bottom: 4, top: 4),
                        child: TouchableScale(
                          onTap: () {
                            HapticFeedback.selectionClick();
                            setState(() {
                              _selectedCategory = isSelected ? '' : catName;
                            });
                          },
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                            decoration: BoxDecoration(
                              color: isSelected ? AppTheme.netflixRed : const Color(0xFF181822),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(
                                color: isSelected
                                    ? AppTheme.netflixRed
                                    : Colors.white.withValues(alpha: 0.08),
                              ),
                            ),
                            child: Center(
                              child: Text(
                                isAll ? l10n.filterAll : catName,
                                style: TextStyle(
                                  color: isSelected ? Colors.white : Colors.white70,
                                  fontSize: 12.5,
                                  fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                                ),
                              ),
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                );
              },
              loading: () => const SizedBox(height: 44),
              error: (_, __) => const SizedBox.shrink(),
            ),

            // Suggestions rapides si la recherche est vide
            if (query.isEmpty && _selectedCategory.isEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                child: Row(
                  children: [
                    const Icon(Icons.trending_up, color: AppTheme.netflixRed, size: 16),
                    const SizedBox(width: 6),
                    Text(
                      'Recherches populaires :',
                      style: TextStyle(color: Colors.white.withValues(alpha: 0.6), fontSize: 12),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: _popularSuggestions.map((tag) {
                            return Padding(
                              padding: const EdgeInsets.only(right: 6),
                              child: GestureDetector(
                                onTap: () {
                                  HapticFeedback.selectionClick();
                                  _controller.text = tag;
                                  setState(() {});
                                },
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: Colors.white.withValues(alpha: 0.06),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Text(
                                    tag,
                                    style: const TextStyle(color: Colors.white70, fontSize: 11),
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ),
                    ),
                  ],
                ),
              ),

            const SizedBox(height: 4),

            // 3. Résultats de recherche (Séries + Vidéos)
            Expanded(
              child: allVideosAsync.when(
                loading: () => GridView.builder(
                  padding: const EdgeInsets.all(16),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    childAspectRatio: 0.68,
                    crossAxisSpacing: 10,
                    mainAxisSpacing: 12,
                  ),
                  itemCount: 9,
                  itemBuilder: (_, __) => const ShimmerBox(borderRadius: 8),
                ),
                error: (err, _) => Center(
                  child: Text('Erreur : $err', style: const TextStyle(color: Colors.white60)),
                ),
                data: (allVideos) {
                  var filtered = allVideos;

                  if (_selectedCategory.isNotEmpty) {
                    filtered = filtered
                        .where((v) => v.category.toLowerCase() == _selectedCategory.toLowerCase())
                        .toList();
                  }

                  if (query.isNotEmpty) {
                    filtered = filtered.where((v) {
                      final titleMatch = v.title.toLowerCase().contains(query);
                      final captionMatch = (v.caption ?? '').toLowerCase().contains(query);
                      final catMatch = v.category.toLowerCase().contains(query);
                      return titleMatch || captionMatch || catMatch;
                    }).toList();
                  }

                  // Séries correspondantes depuis seriesListAsync
                  final matchingSeries = seriesListAsync.maybeWhen(
                    data: (seriesList) {
                      if (query.isEmpty) return seriesList;
                      return seriesList.where((s) {
                        final titleFr = s.titleFr.toLowerCase();
                        final titleAr = (s.titleAr ?? '').toLowerCase();
                        final titleEn = (s.titleEn ?? '').toLowerCase();
                        final hasGenre = s.genres.any((g) => g.toLowerCase().contains(query));
                        return titleFr.contains(query) ||
                            titleAr.contains(query) ||
                            titleEn.contains(query) ||
                            hasGenre;
                      }).toList();
                    },
                    orElse: () => <SeriesDetailModel>[],
                  );

                  if (filtered.isEmpty && matchingSeries.isEmpty) {
                    return EmptyStateView(
                      icon: Icons.search_off_rounded,
                      title: query.isNotEmpty
                          ? l10n.noResultsFor(query)
                          : 'Aucun contenu trouvé',
                      subtitle: 'Essayez avec un autre mot-clé ou sélectionnez une autre catégorie.',
                      actionLabel: query.isNotEmpty ? 'Effacer la recherche' : null,
                      onAction: query.isNotEmpty
                          ? () {
                              _controller.clear();
                              setState(() {
                                _selectedCategory = '';
                              });
                            }
                          : null,
                    );
                  }

                  return FutureBuilder<String>(
                    future: storageService.getServerUrl(),
                    builder: (context, snapshot) {
                      final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;

                      return CustomScrollView(
                        slivers: [
                          // Section Séries trouvées
                          if (matchingSeries.isNotEmpty) ...[
                            SliverToBoxAdapter(
                              child: Padding(
                                padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                                child: Text(
                                  l10n.filterSeries,
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ),
                            SliverToBoxAdapter(
                              child: SizedBox(
                                height: 160,
                                child: ListView.builder(
                                  scrollDirection: Axis.horizontal,
                                  padding: const EdgeInsets.symmetric(horizontal: 16),
                                  itemCount: matchingSeries.length,
                                  itemBuilder: (context, index) {
                                    final s = matchingSeries[index];
                                    final sTitle = s.getLocalizedTitle(langCode);
                                    final posterUrl = ImageUtils.resolveUrl(s.posterPath, baseUrl);

                                    return Container(
                                      width: 100,
                                      margin: const EdgeInsets.only(right: 10),
                                      child: TouchableScale(
                                        onTap: () {
                                          Navigator.push(
                                            context,
                                            MaterialPageRoute(
                                              builder: (_) => SeriesDetailScreen(
                                                seriesId: s.id,
                                                initialTitle: sTitle,
                                                initialPoster: s.posterPath,
                                              ),
                                            ),
                                          );
                                        },
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            ClipRRect(
                                              borderRadius: BorderRadius.circular(6),
                                              child: AspectRatio(
                                                aspectRatio: 2 / 3,
                                                child: (posterUrl != null && posterUrl.isNotEmpty)
                                                    ? CachedNetworkImage(
                                                        imageUrl: posterUrl,
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
                                            const SizedBox(height: 4),
                                            Text(
                                              sTitle,
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style: const TextStyle(
                                                color: Colors.white,
                                                fontSize: 11.5,
                                                fontWeight: FontWeight.w600,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                    );
                                  },
                                ),
                              ),
                            ),
                            const SliverToBoxAdapter(child: SizedBox(height: 8)),
                          ],

                          // Section Vidéos / Épisodes
                          if (filtered.isNotEmpty) ...[
                            if (matchingSeries.isNotEmpty)
                              const SliverToBoxAdapter(
                                child: Padding(
                                  padding: EdgeInsets.fromLTRB(16, 8, 16, 8),
                                  child: Text(
                                    'Vidéos & Épisodes',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                              ),
                            SliverPadding(
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              sliver: SliverGrid(
                                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                                  crossAxisCount: 3,
                                  childAspectRatio: 0.68,
                                  crossAxisSpacing: 10,
                                  mainAxisSpacing: 12,
                                ),
                                delegate: SliverChildBuilderDelegate(
                                  (context, index) {
                                    final video = filtered[index];
                                    return TouchableScale(
                                      onTap: () => _onVideoSelected(video, filtered),
                                      child: VideoCard(
                                        video: video,
                                        heroTag: 'search_video_${video.id}',
                                        onTap: () => _onVideoSelected(video, filtered),
                                      ),
                                    );
                                  },
                                  childCount: filtered.length,
                                ),
                              ),
                            ),
                          ],
                        ],
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
