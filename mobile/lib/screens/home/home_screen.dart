import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants/api_constants.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/image_utils.dart';
import '../../models/home_model.dart';
import '../../models/video_model.dart';
import '../../providers/video_provider.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/error_state.dart';
import '../../widgets/hero_slider.dart';
import '../../widgets/shimmer_placeholder.dart';
import '../../widgets/top_number_card.dart';
import '../../widgets/touchable_scale.dart';
import '../../widgets/video_card.dart';
import '../player/reels_screen.dart';
import '../series/series_detail_screen.dart';

/// Écran d'accueil immersif moderne pour VidTele / Atlas Play.
/// Intègre :
/// - Slider Héro des séries avec lecture auto (5s), pause au toucher, indicateurs animés
/// - Section Top 5 des séries avec grands chiffres stylisés Netflix
/// - Rangées horizontales : Continuer la lecture, Nouveautés, Tendances, Séries, Par genre
/// - Shimmer loading, pull-to-refresh et gestion d'erreurs soignée
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  bool _isSearching = false;
  final _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
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

  void _onSeriesSelected(int seriesId, String title, String? posterPath) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => SeriesDetailScreen(
          seriesId: seriesId,
          initialTitle: title,
          initialPoster: posterPath,
        ),
      ),
    );
  }

  Future<void> _refreshAll() async {
    ref.invalidate(homeDataProvider);
    ref.invalidate(videoListProvider);
    ref.invalidate(categoriesProvider);
    ref.invalidate(seriesListProvider);
  }

  @override
  Widget build(BuildContext context) {
    final homeDataAsync = ref.watch(homeDataProvider);
    final seriesListAsync = ref.watch(seriesListProvider);
    final searchResults = ref.watch(searchResultsProvider);
    final l10n = context.l10n;

    return Scaffold(
      backgroundColor: AppTheme.darkBackground,
      body: RefreshIndicator(
        color: AppTheme.netflixRed,
        backgroundColor: AppTheme.darkSurface,
        onRefresh: _refreshAll,
        child: CustomScrollView(
          physics: const AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics()),
          slivers: [
            // 1. Barre d'application transparente stylisée
            SliverAppBar(
              floating: true,
              pinned: true,
              backgroundColor: AppTheme.darkBackground.withValues(alpha: 0.92),
              elevation: 0,
              title: _isSearching
                  ? TextField(
                      controller: _searchController,
                      autofocus: true,
                      style: const TextStyle(color: Colors.white),
                      decoration: InputDecoration(
                        hintText: l10n.searchPlaceholder,
                        hintStyle: const TextStyle(color: Colors.white54, fontSize: 14),
                        border: InputBorder.none,
                        prefixIcon: const Icon(Icons.search, color: Colors.white70),
                      ),
                      onChanged: (val) {
                        ref.read(searchQueryProvider.notifier).state = val;
                      },
                    )
                  : Row(
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(6),
                          child: Image.asset(
                            'assets/images/atlas_play_icon.png',
                            width: 28,
                            height: 28,
                            fit: BoxFit.cover,
                          ),
                        ),
                        const SizedBox(width: 10),
                        RichText(
                          text: const TextSpan(
                            children: [
                              TextSpan(
                                text: 'ATLAS ',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w900,
                                  letterSpacing: 2,
                                  fontSize: 18,
                                ),
                              ),
                              TextSpan(
                                text: 'PLAY',
                                style: TextStyle(
                                  color: AppTheme.netflixRed,
                                  fontWeight: FontWeight.w900,
                                  letterSpacing: 2,
                                  fontSize: 18,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
              actions: [
                IconButton(
                  icon: Icon(_isSearching ? Icons.close : Icons.search, color: Colors.white),
                  tooltip: _isSearching ? 'Fermer' : l10n.search,
                  onPressed: () {
                    setState(() {
                      _isSearching = !_isSearching;
                      if (!_isSearching) {
                        _searchController.clear();
                        ref.read(searchQueryProvider.notifier).state = '';
                      }
                    });
                  },
                ),
                IconButton(
                  icon: const Icon(Icons.refresh, color: Colors.white70),
                  tooltip: l10n.refresh,
                  onPressed: _refreshAll,
                ),
              ],
            ),

            // 2. Mode Recherche active : grille de résultats
            if (_isSearching)
              SliverPadding(
                padding: const EdgeInsets.all(16),
                sliver: searchResults.isEmpty
                    ? SliverToBoxAdapter(
                        child: Padding(
                          padding: const EdgeInsets.only(top: 60),
                          child: EmptyStateView(
                            icon: Icons.search_off_rounded,
                            title: l10n.noResultsFor(_searchController.text),
                          ),
                        ),
                      )
                    : SliverGrid(
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 3,
                          childAspectRatio: 0.65,
                          crossAxisSpacing: 10,
                          mainAxisSpacing: 12,
                        ),
                        delegate: SliverChildBuilderDelegate(
                          (context, index) {
                            final video = searchResults[index];
                            return VideoCard(
                              video: video,
                              onTap: () => _onVideoSelected(video),
                            );
                          },
                          childCount: searchResults.length,
                        ),
                      ),
              )
            else
              // 3. Contenu principal de la page d'accueil
              homeDataAsync.when(
                loading: () => SliverToBoxAdapter(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const ShimmerHeroBanner(),
                      const SizedBox(height: 20),
                      _buildSectionHeader(l10n.top5Series),
                      const ShimmerVideoRow(cardWidth: 155, cardHeight: 200, count: 3),
                      const SizedBox(height: 24),
                      _buildSectionHeader(l10n.continueWatching),
                      const ShimmerVideoRow(),
                      const SizedBox(height: 24),
                      _buildSectionHeader(l10n.newReleases),
                      const ShimmerVideoRow(),
                    ],
                  ),
                ),
                error: (err, _) => SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.only(top: 100),
                    child: ErrorStateView(
                      message: l10n.catalogLoadError,
                      onRetry: _refreshAll,
                    ),
                  ),
                ),
                data: (homeData) {
                  return SliverToBoxAdapter(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // A. Slider Héro cinématique des dernières séries
                        if (homeData.hero.isNotEmpty)
                          HeroSlider(
                            items: homeData.hero,
                            onWatch: (heroItem) {
                              _onSeriesSelected(
                                heroItem.id,
                                heroItem.titleFr ?? heroItem.title,
                                heroItem.posterPath,
                              );
                            },
                          )
                        else
                          // Fallback si la liste hero est vide : featured video
                          ref.watch(featuredVideoProvider) != null
                              ? _buildSingleHeroBanner(ref.watch(featuredVideoProvider)!, l10n)
                              : const SizedBox.shrink(),

                        const SizedBox(height: 16),

                        // B. Section "Continuer la lecture" (si historique en cours)
                        _buildContinueWatchingSection(homeData, l10n),

                        // C. Section "Top 5 des séries" (chiffres géants Netflix 1 à 5)
                        _buildTop5SeriesSection(homeData, l10n),

                        // D. Rangée "Nouveautés"
                        if (homeData.newReleases.isNotEmpty) ...[
                          _buildSectionHeader(l10n.newReleases),
                          _buildHorizontalVideoList(homeData.newReleases),
                          const SizedBox(height: 24),
                        ],

                        // E. Rangée "Tendances"
                        if (homeData.trending.isNotEmpty) ...[
                          _buildSectionHeader(l10n.trendingNow),
                          _buildHorizontalVideoList(homeData.trending),
                          const SizedBox(height: 24),
                        ],

                        // F. Section Catalogue complet des Séries TV
                        _buildSeriesCatalogSection(seriesListAsync, l10n),

                        // G. Rangées Dynamiques par Genre / Catégorie
                        if (homeData.genres.isNotEmpty)
                          ...homeData.genres.map((genre) {
                            if (genre.items.isEmpty) return const SizedBox.shrink();
                            return Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                _buildSectionHeader('${genre.name} (${genre.count})'),
                                _buildHorizontalVideoList(genre.items),
                                const SizedBox(height: 24),
                              ],
                            );
                          })
                        else
                          // Fallback sur le catalogue vidéo classique par catégorie
                          _buildFallbackCategoriesSection(),

                        const SizedBox(height: 36),
                      ],
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  /// Titre de section stylisé avec typography du design system
  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(left: 16, right: 16, bottom: 12),
      child: Text(
        title,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 18,
          fontWeight: FontWeight.w800,
          letterSpacing: 0.3,
        ),
      ),
    );
  }

  /// Rangée horizontale standard de vidéos
  Widget _buildHorizontalVideoList(List<VideoModel> videos) {
    return SizedBox(
      height: 195,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: videos.length,
        itemBuilder: (context, index) {
          final vid = videos[index];
          return VideoCard(
            video: vid,
            width: 135,
            height: 190,
            onTap: () => _onVideoSelected(vid, videos),
          );
        },
      ),
    );
  }

  /// Section "Continuer la lecture" avec barre de progression
  Widget _buildContinueWatchingSection(HomeScreenData homeData, AppLocalizations l10n) {
    final list = homeData.continueWatching.isNotEmpty
        ? homeData.continueWatching
        : ref.watch(continueWatchingProvider);

    if (list.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader(l10n.continueWatching),
        SizedBox(
          height: 195,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: list.length,
            itemBuilder: (context, index) {
              final vid = list[index];
              return VideoCard(
                video: vid,
                showProgress: true,
                width: 135,
                height: 190,
                onTap: () => _onVideoSelected(vid, list),
              );
            },
          ),
        ),
        const SizedBox(height: 24),
      ],
    );
  }

  /// Section "Top 5 des Séries" (avec grands chiffres Netflix 1 à 5)
  Widget _buildTop5SeriesSection(HomeScreenData homeData, AppLocalizations l10n) {
    final topSeries = homeData.top5;

    if (topSeries.isNotEmpty) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader(l10n.top5Series),
          SizedBox(
            height: 200,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: topSeries.length,
              itemBuilder: (context, index) {
                final s = topSeries[index];
                return TopNumberCard.fromSeries(
                  rank: index + 1,
                  series: s,
                  onTap: () => _onSeriesSelected(s.id, s.titleFr ?? s.title, s.posterPath),
                );
              },
            ),
          ),
          const SizedBox(height: 24),
        ],
      );
    }

    // Fallback si pas de top5 séries : top5 vidéos
    final top5Videos = ref.watch(top5VideosProvider);
    if (top5Videos.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader(l10n.top5Trending),
        SizedBox(
          height: 200,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: top5Videos.length,
            itemBuilder: (context, index) {
              final vid = top5Videos[index];
              return TopNumberCard.fromVideo(
                rank: index + 1,
                video: vid,
                onTap: () => _onVideoSelected(vid, top5Videos),
              );
            },
          ),
        ),
        const SizedBox(height: 24),
      ],
    );
  }

  /// Section Catalogue des Séries TV
  Widget _buildSeriesCatalogSection(
    AsyncValue<List<dynamic>> seriesListAsync,
    AppLocalizations l10n,
  ) {
    return seriesListAsync.when(
      data: (seriesList) {
        if (seriesList.isEmpty) return const SizedBox.shrink();

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSectionHeader(l10n.series),
            SizedBox(
              height: 205,
              child: FutureBuilder<String>(
                future: storageService.getServerUrl(),
                builder: (context, snapshot) {
                  final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;

                  return ListView.builder(
                    scrollDirection: Axis.horizontal,
                    physics: const BouncingScrollPhysics(),
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemCount: seriesList.length,
                    itemBuilder: (context, index) {
                      final s = seriesList[index];
                      final posterUrl = ImageUtils.resolveUrl(s.posterPath ?? s.bannerPath, baseUrl);

                      return TouchableScale(
                        onTap: () => _onSeriesSelected(s.id, s.titleFr ?? s.title, s.posterPath),
                        child: Container(
                          width: 135,
                          margin: const EdgeInsets.only(right: 12),
                          decoration: BoxDecoration(
                            color: AppTheme.darkSurface,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: Colors.white.withValues(alpha: 0.08),
                              width: 1,
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withValues(alpha: 0.5),
                                blurRadius: 6,
                                offset: const Offset(0, 3),
                              ),
                            ],
                          ),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: Stack(
                              fit: StackFit.expand,
                              children: [
                                if (posterUrl != null && posterUrl.isNotEmpty)
                                  CachedNetworkImage(
                                    imageUrl: posterUrl,
                                    fit: BoxFit.cover,
                                    placeholder: (context, url) => Container(color: AppTheme.darkSurfaceLight),
                                    errorWidget: (context, url, error) => Container(
                                      color: AppTheme.darkSurfaceLight,
                                      child: const Icon(Icons.tv, size: 40, color: Colors.white24),
                                    ),
                                  )
                                else
                                  Container(
                                    color: AppTheme.darkSurfaceLight,
                                    child: const Icon(Icons.tv, size: 40, color: Colors.white24),
                                  ),
                                Positioned.fill(
                                  child: Container(
                                    decoration: BoxDecoration(
                                      gradient: LinearGradient(
                                        begin: Alignment.topCenter,
                                        end: Alignment.bottomCenter,
                                        colors: [
                                          Colors.transparent,
                                          Colors.black.withValues(alpha: 0.85),
                                        ],
                                        stops: const [0.55, 1.0],
                                      ),
                                    ),
                                  ),
                                ),
                                Positioned(
                                  bottom: 8,
                                  left: 8,
                                  right: 8,
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(
                                        s.titleFr ?? s.title,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 12.5,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                      if (s.seasonsCount != null)
                                        Text(
                                          '${s.seasonsCount} saison(s) · ${s.episodesCount ?? 0} ép.',
                                          style: const TextStyle(
                                            color: Colors.white60,
                                            fontSize: 10,
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
            const SizedBox(height: 24),
          ],
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }

  /// Fallback par catégories si homeData.genres est vide
  Widget _buildFallbackCategoriesSection() {
    final categoriesAsync = ref.watch(categoriesProvider);

    return categoriesAsync.when(
      data: (categories) {
        return Column(
          children: categories.map((cat) {
            return Consumer(
              builder: (context, ref, _) {
                final catVideos = ref.watch(videosByCategoryProvider(cat.name));
                if (catVideos.isEmpty) return const SizedBox.shrink();

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildSectionHeader('${cat.name} (${cat.count})'),
                    _buildHorizontalVideoList(catVideos),
                    const SizedBox(height: 24),
                  ],
                );
              },
            );
          }).toList(),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
    );
  }

  /// Bannière unique de secours si aucune série hero n'est disponible
  Widget _buildSingleHeroBanner(VideoModel video, AppLocalizations l10n) {
    return FutureBuilder<String>(
      future: storageService.getServerUrl(),
      builder: (context, snapshot) {
        final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;
        final thumbUrl = ImageUtils.resolveUrl(video.thumbnailPath, baseUrl);

        return Stack(
          alignment: Alignment.bottomCenter,
          children: [
            SizedBox(
              height: 440,
              width: double.infinity,
              child: thumbUrl != null
                  ? CachedNetworkImage(
                      imageUrl: thumbUrl,
                      fit: BoxFit.cover,
                      errorWidget: (context, url, error) =>
                          Container(color: AppTheme.darkSurface),
                    )
                  : Container(
                      color: AppTheme.darkSurface,
                      child: const Center(
                        child: Icon(Icons.movie, size: 100, color: Colors.white24),
                      ),
                    ),
            ),
            Container(
              height: 440,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.transparent,
                    Colors.transparent,
                    Color(0xCC09090C),
                    AppTheme.netflixBlack,
                  ],
                  stops: [0.0, 0.45, 0.75, 1.0],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.netflixRed.withValues(alpha: 0.9),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '#${video.category.toUpperCase()}',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 1.2,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    video.title,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      shadows: [
                        Shadow(color: Colors.black, blurRadius: 10, offset: Offset(0, 2)),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      ElevatedButton.icon(
                        onPressed: () {
                          final allVids = ref.read(videoListProvider).value ?? [];
                          _onVideoSelected(video, allVids);
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                        ),
                        icon: const Icon(Icons.play_arrow, size: 28),
                        label: Text(
                          l10n.play,
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}
