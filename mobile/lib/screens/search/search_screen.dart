import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/theme/app_theme.dart';
import '../../models/video_model.dart';
import '../../providers/video_provider.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/shimmer_placeholder.dart';
import '../../widgets/touchable_scale.dart';
import '../../widgets/video_card.dart';
import '../player/video_player_screen.dart';

/// Écran dédié à la recherche et à l'exploration par catégorie / genre
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final TextEditingController _controller = TextEditingController();
  String _selectedCategory = '';

  @override
  void dispose() {
    _controller.dispose();
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
    final l10n = context.l10n;
    final allVideosAsync = ref.watch(videoListProvider);
    final categoriesAsync = ref.watch(categoriesProvider);
    final query = _controller.text.trim().toLowerCase();

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      body: SafeArea(
        child: Column(
          children: [
            // 1. Barre de recherche moderne
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
                                isAll ? 'Tout' : catName,
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

            const SizedBox(height: 8),

            // 3. Résultats de recherche en grille
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

                  if (filtered.isEmpty) {
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

                  return GridView.builder(
                    padding: const EdgeInsets.all(16),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 3,
                      childAspectRatio: 0.68,
                      crossAxisSpacing: 10,
                      mainAxisSpacing: 12,
                    ),
                    itemCount: filtered.length,
                    itemBuilder: (context, index) {
                      final video = filtered[index];
                      return VideoCard(
                        video: video,
                        heroTag: 'search_video_${video.id}',
                        onTap: () => _onVideoSelected(video, filtered),
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
