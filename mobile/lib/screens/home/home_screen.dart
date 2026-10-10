import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants/api_constants.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/image_utils.dart';
import '../../models/video_model.dart';
import '../../providers/video_provider.dart';
import '../../widgets/top_number_card.dart';
import '../../widgets/video_card.dart';
import '../player/video_player_screen.dart';

/// Écran d'accueil immersif style Netflix pour VidTele.
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
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => VideoPlayerScreen(
          video: video,
          playlist: playlist,
          initialIndex: playlist?.indexOf(video),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final videoListAsync = ref.watch(videoListProvider);
    final featuredVideo = ref.watch(featuredVideoProvider);
    final continueWatching = ref.watch(continueWatchingProvider);
    final top5Videos = ref.watch(top5VideosProvider);
    final categoriesAsync = ref.watch(categoriesProvider);
    final searchResults = ref.watch(searchResultsProvider);
    final l10n = context.l10n;

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      body: RefreshIndicator(
        color: AppTheme.netflixRed,
        backgroundColor: AppTheme.netflixDarkGray,
        onRefresh: () async {
          ref.invalidate(videoListProvider);
          ref.invalidate(categoriesProvider);
        },
        child: CustomScrollView(
          slivers: [
            // 1. Barre d'application transparente style Netflix
            SliverAppBar(
              floating: true,
              pinned: true,
              backgroundColor: Colors.black.withValues(alpha: 0.9),
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
                        const SizedBox(width: 9),
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
                  onPressed: () {
                    ref.invalidate(videoListProvider);
                    ref.invalidate(categoriesProvider);
                  },
                ),
              ],
            ),

            // 2. Si l'utilisateur est en train de chercher : afficher les résultats en grille
            if (_isSearching)
              SliverPadding(
                padding: const EdgeInsets.all(16),
                sliver: searchResults.isEmpty
                    ? SliverToBoxAdapter(
                        child: Padding(
                          padding: const EdgeInsets.only(top: 60),
                          child: Center(
                            child: Column(
                              children: [
                                const Icon(Icons.search_off, size: 54, color: Colors.white38),
                                const SizedBox(height: 12),
                                Text(
                                  l10n.noResultsFor(_searchController.text),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(color: Colors.white60, fontSize: 15),
                                ),
                              ],
                            ),
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
            else ...[
              // 3. Bannière Hero (Vidéo mise en avant tout en haut façon Netflix)
              if (featuredVideo != null)
                SliverToBoxAdapter(
                  child: _buildHeroBanner(featuredVideo, l10n),
                )
              else
                SliverToBoxAdapter(
                  child: videoListAsync.when(
                    loading: () => const SizedBox(
                      height: 380,
                      child: Center(
                        child: CircularProgressIndicator(color: AppTheme.netflixRed),
                      ),
                    ),
                    error: (err, _) => SizedBox(
                      height: 250,
                      child: Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.wifi_off, color: Colors.redAccent, size: 40),
                            const SizedBox(height: 8),
                            Text(
                              l10n.catalogLoadError,
                              style: const TextStyle(color: Colors.white70),
                            ),
                            const SizedBox(height: 12),
                            ElevatedButton(
                              onPressed: () => ref.invalidate(videoListProvider),
                              child: Text(l10n.retry),
                            ),
                          ],
                        ),
                      ),
                    ),
                    data: (_) => const SizedBox.shrink(),
                  ),
                ),

              // 4. Contenu déroulant façon Netflix
              SliverToBoxAdapter(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(height: 18),

                    // 0. Slider / Carousel des Dernières Séries Ajoutées
                    _buildLatestSeriesSlider(l10n),

                    // A. Rangée "Continuer la lecture" (si historique en cours)
                    if (continueWatching.isNotEmpty) ...[
                      _buildSectionHeader(l10n.continueWatching),
                      SizedBox(
                        height: 195,
                        child: ListView.builder(
                          scrollDirection: Axis.horizontal,
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: continueWatching.length,
                          itemBuilder: (context, index) {
                            final vid = continueWatching[index];
                            return VideoCard(
                              video: vid,
                              showProgress: true,
                              width: 135,
                              height: 190,
                              onTap: () => _onVideoSelected(vid, continueWatching),
                            );
                          },
                        ),
                      ),
                      const SizedBox(height: 24),
                    ],

                    // B. Rangée "Top 5 des Tendances" (grands chiffres Netflix)
                    if (top5Videos.isNotEmpty) ...[
                      _buildSectionHeader(l10n.top5Trending),
                      SizedBox(
                        height: 200,
                        child: ListView.builder(
                          scrollDirection: Axis.horizontal,
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: top5Videos.length,
                          itemBuilder: (context, index) {
                            final vid = top5Videos[index];
                            return TopNumberCard(
                              rank: index + 1,
                              video: vid,
                              onTap: () => _onVideoSelected(vid, top5Videos),
                            );
                          },
                        ),
                      ),
                      const SizedBox(height: 24),
                    ],

                    // C. Rangées Dynamiques par Catégorie (Films, Séries, etc.)
                    categoriesAsync.when(
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
                                    SizedBox(
                                      height: 195,
                                      child: ListView.builder(
                                        scrollDirection: Axis.horizontal,
                                        padding: const EdgeInsets.symmetric(horizontal: 16),
                                        itemCount: catVideos.length,
                                        itemBuilder: (context, index) {
                                          final vid = catVideos[index];
                                          return VideoCard(
                                            video: vid,
                                            width: 135,
                                            height: 190,
                                            onTap: () => _onVideoSelected(vid, catVideos),
                                          );
                                        },
                                      ),
                                    ),
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
                    ),
                    const SizedBox(height: 32),
                  ],
                ),
              ),

            ],
          ],
        ),
      ),
    );
  }

  /// Titre de section stylisé
  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(left: 16, right: 16, bottom: 10),
      child: Text(
        title,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 18,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.3,
        ),
      ),
    );
  }

  /// Section Slider / Carousel des Dernières Séries Ajoutées
  Widget _buildLatestSeriesSlider(AppLocalizations l10n) {
    final latestSeriesAsync = ref.watch(latestSeriesProvider);
    final videoList = ref.watch(videoListProvider).value ?? [];

    return latestSeriesAsync.when(
      data: (seriesList) {
        if (seriesList.isEmpty) return const SizedBox.shrink();

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSectionHeader(l10n.latestSeriesTitle),
            SizedBox(
              height: 220,
              child: FutureBuilder<String>(
                future: storageService.getServerUrl(),
                builder: (context, snapshot) {
                  final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;

                  return ListView.builder(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemCount: seriesList.length,
                    itemBuilder: (context, index) {
                      final s = seriesList[index];
                      final posterUrl = ImageUtils.resolveUrl(s.posterPath ?? s.bannerPath, baseUrl);

                      return GestureDetector(
                        onTap: () {
                          if (s.firstVideoId != null) {
                            final targetVid = videoList.firstWhere(
                              (v) => v.id == s.firstVideoId,
                              orElse: () => VideoModel(
                                id: s.firstVideoId!,
                                telegramMessageId: 0,
                                title: s.title,
                                category: 'Série',
                                durationSeconds: 0,
                                fileSizeBytes: 0,
                                mimeType: 'video/mp4',
                                thumbnailPath: s.posterPath,
                                viewsCount: 0,
                                isFavorite: false,
                                watchProgressSeconds: 0.0,
                                isCompleted: false,
                              ),
                            );
                            _onVideoSelected(targetVid, videoList);
                          }
                        },
                        child: Container(
                          width: 145,
                          margin: const EdgeInsets.only(right: 12),
                          decoration: BoxDecoration(
                            color: AppTheme.netflixCard,
                            borderRadius: BorderRadius.circular(8),
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
                                posterUrl != null
                                    ? CachedNetworkImage(
                                        imageUrl: posterUrl,
                                        fit: BoxFit.cover,
                                        placeholder: (context, url) => Container(
                                          color: const Color(0xFF1F1F1F),
                                          child: const Center(
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                              color: AppTheme.netflixRed,
                                            ),
                                          ),
                                        ),
                                        errorWidget: (context, url, error) => Container(
                                          color: const Color(0xFF1F1F1F),
                                          child: const Icon(Icons.tv, size: 40, color: Colors.white24),
                                        ),
                                      )
                                    : Container(
                                        color: const Color(0xFF1F1F1F),
                                        child: const Icon(Icons.tv, size: 40, color: Colors.white24),
                                      ),
                                Positioned.fill(
                                  child: Container(
                                    decoration: const BoxDecoration(
                                      gradient: LinearGradient(
                                        colors: [
                                          Colors.transparent,
                                          Colors.transparent,
                                          Color(0xCC000000),
                                          Colors.black,
                                        ],
                                        begin: Alignment.topCenter,
                                        end: Alignment.bottomCenter,
                                      ),
                                    ),
                                  ),
                                ),
                                if (s.rating != null)
                                  Positioned(
                                    top: 6,
                                    right: 6,
                                    child: Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: Colors.black.withValues(alpha: 0.75),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          const Icon(Icons.star, color: Colors.amber, size: 12),
                                          const SizedBox(width: 2),
                                          Text(
                                            s.rating!.toStringAsFixed(1),
                                            style: const TextStyle(
                                              color: Colors.white,
                                              fontSize: 10,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                Positioned(
                                  left: 8,
                                  right: 8,
                                  bottom: 8,
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(
                                        s.title,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 12,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                      if (s.year != null)
                                        Text(
                                          '${s.year}',
                                          style: const TextStyle(color: Colors.white54, fontSize: 10),
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

  /// Affiche principale Hero Banner
  Widget _buildHeroBanner(VideoModel video, AppLocalizations l10n) {
    return FutureBuilder<String>(
      future: storageService.getServerUrl(),
      builder: (context, snapshot) {
        final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;
        final thumbUrl = ImageUtils.resolveUrl(video.thumbnailPath, baseUrl);

        return Stack(
          alignment: Alignment.bottomCenter,
          children: [
            // Affiche en arrière-plan
            SizedBox(
              height: 440,
              width: double.infinity,
              child: thumbUrl != null
                  ? CachedNetworkImage(
                      imageUrl: thumbUrl,
                      fit: BoxFit.cover,
                      errorWidget: (context, url, error) =>
                          Container(color: const Color(0xFF1F1F1F)),
                    )
                  : Container(
                      color: const Color(0xFF1F1F1F),
                      child: const Center(
                        child: Icon(Icons.movie, size: 100, color: Colors.white24),
                      ),
                    ),
            ),

            // Dégradé noir vertical (du transparent au noir pur façon Netflix)
            Container(
              height: 440,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.transparent,
                    Colors.transparent,
                    Color(0xCC000000),
                    AppTheme.netflixBlack,
                  ],
                  stops: [0.0, 0.45, 0.75, 1.0],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
            ),

            // Métadonnées & Boutons centrés en bas de la bannière
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Badge Catégorie
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

                  // Titre du contenu
                  Text(
                    video.title,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.5,
                      shadows: [
                        Shadow(color: Colors.black, blurRadius: 10, offset: Offset(0, 2)),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Boutons d'action Hero
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      // Bouton Lecture blanc (Style Netflix)
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
                      const SizedBox(width: 16),

                      // Bouton Info / Détails
                      OutlinedButton.icon(
                        onPressed: () {
                          final allVids = ref.read(videoListProvider).value ?? [];
                          _onVideoSelected(video, allVids);
                        },
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.white,
                          side: const BorderSide(color: Colors.white54),
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                        ),
                        icon: const Icon(Icons.info_outline, size: 22),
                        label: Text(l10n.details),
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
