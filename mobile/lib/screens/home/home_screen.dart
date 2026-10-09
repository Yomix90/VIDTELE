import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants/api_constants.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../models/video_model.dart';
import '../../providers/auth_provider.dart';
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

  void _onVideoSelected(VideoModel video) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => VideoPlayerScreen(video: video),
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
                      decoration: const InputDecoration(
                        hintText: 'Rechercher un film, une série, un hashtag...',
                        hintStyle: TextStyle(color: Colors.white54, fontSize: 14),
                        border: InputBorder.none,
                        prefixIcon: Icon(Icons.search, color: Colors.white70),
                      ),
                      onChanged: (val) {
                        ref.read(searchQueryProvider.notifier).state = val;
                      },
                    )
                  : Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                          decoration: BoxDecoration(
                            color: AppTheme.netflixRed,
                            borderRadius: BorderRadius.circular(3),
                          ),
                          child: const Text(
                            'V',
                            style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 20),
                          ),
                        ),
                        const SizedBox(width: 8),
                        const Text(
                          'VIDTELE',
                          style: TextStyle(
                            color: AppTheme.netflixRed,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 1.5,
                            fontSize: 20,
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
                  icon: const Icon(Icons.logout, color: Colors.white70),
                  tooltip: 'Déconnexion',
                  onPressed: () {
                    ref.read(authProvider.notifier).logout();
                  },
                ),
              ],
            ),

            // 2. Vue Résultats de recherche si recherche active
            if (_isSearching && _searchController.text.isNotEmpty)
              SliverPadding(
                padding: const EdgeInsets.all(16),
                sliver: searchResults.isEmpty
                    ? const SliverToBoxAdapter(
                        child: Center(
                          child: Padding(
                            padding: EdgeInsets.only(top: 80),
                            child: Text(
                              'Aucune vidéo trouvée pour cette recherche.',
                              style: TextStyle(color: Colors.white60, fontSize: 16),
                            ),
                          ),
                        ),
                      )
                    : SliverGrid(
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 2,
                          childAspectRatio: 0.7,
                          crossAxisSpacing: 12,
                          mainAxisSpacing: 12,
                        ),
                        delegate: SliverChildBuilderDelegate(
                          (context, index) {
                            final vid = searchResults[index];
                            return VideoCard(
                              video: vid,
                              onTap: () => _onVideoSelected(vid),
                              width: double.infinity,
                              height: double.infinity,
                            );
                          },
                          childCount: searchResults.length,
                        ),
                      ),
              )
            else
              // 3. Contenu d'accueil classique style Netflix
              SliverList(
                delegate: SliverChildListDelegate([
                  // A. Grande Bannière Hero en Vedette (Featured Video)
                  if (featuredVideo != null)
                    _buildHeroBanner(featuredVideo)
                  else if (videoListAsync.isLoading)
                    Container(
                      height: 420,
                      color: const Color(0xFF1E1E1E),
                      child: const Center(
                        child: CircularProgressIndicator(color: AppTheme.netflixRed),
                      ),
                    ),

                  const SizedBox(height: 18),

                  // B. Rangée "Continuer la lecture" (si historique en cours)
                  if (continueWatching.isNotEmpty) ...[
                    _buildSectionHeader('Continuer la lecture'),
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
                            onTap: () => _onVideoSelected(vid),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 24),
                  ],

                  // C. Rangée "Top 5 des Tendances" (grands chiffres Netflix)
                  if (top5Videos.isNotEmpty) ...[
                    _buildSectionHeader('Top 5 des Vidéos les plus regardées'),
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
                            onTap: () => _onVideoSelected(vid),
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 24),
                  ],

                  // D. Rangées Dynamiques par Catégorie (Films, Séries, etc.)
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
                                          onTap: () => _onVideoSelected(vid),
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

                  const SizedBox(height: 60),
                ]),
              ),
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

  /// Affiche principale Hero Banner
  Widget _buildHeroBanner(VideoModel video) {
    return FutureBuilder<String>(
      future: storageService.getServerUrl(),
      builder: (context, snapshot) {
        final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;
        final thumbUrl = video.thumbnailPath != null ? '$baseUrl${video.thumbnailPath}' : null;

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
                      errorWidget: (context, url, error) => Container(color: const Color(0xFF1F1F1F)),
                    )
                  : Container(color: const Color(0xFF1F1F1F)),
            ),

            // Dégradé sombre immersif
            Container(
              height: 440,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.transparent,
                    Color(0x33000000),
                    Color(0xCC141414),
                    AppTheme.netflixBlack,
                  ],
                  stops: [0.0, 0.4, 0.8, 1.0],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
            ),

            // Informations & Bouton de lecture
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
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
                        letterSpacing: 1,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),

                  // Titre
                  Text(
                    video.title,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 0.5,
                      shadows: [
                        Shadow(color: Colors.black, blurRadius: 8),
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
                        onPressed: () => _onVideoSelected(video),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                        ),
                        icon: const Icon(Icons.play_arrow, size: 28),
                        label: const Text(
                          'Lecture',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                      ),
                      const SizedBox(width: 16),

                      // Bouton Info
                      OutlinedButton.icon(
                        onPressed: () => _onVideoSelected(video),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: Colors.white,
                          side: const BorderSide(color: Colors.white54),
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                        ),
                        icon: const Icon(Icons.info_outline, size: 22),
                        label: const Text('Détails'),
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
