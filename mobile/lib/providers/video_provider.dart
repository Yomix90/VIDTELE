import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/api_client.dart';
import '../core/constants/api_constants.dart';
import '../models/category_model.dart';
import '../models/video_model.dart';

/// Provider pour charger l'intégralité du catalogue vidéo.
final videoListProvider = FutureProvider.autoDispose<List<VideoModel>>((ref) async {
  final res = await apiClient.dio.get(ApiConstants.videos, queryParameters: {'limit': 100});
  if (res.statusCode == 200) {
    final List items = res.data['items'] ?? [];
    return items.map((e) => VideoModel.fromJson(e)).toList();
  }
  return [];
});

/// Vidéo en vedette pour la grande bannière Hero en haut de l'écran (façon Netflix).
final featuredVideoProvider = Provider.autoDispose<VideoModel?>((ref) {
  final videosAsync = ref.watch(videoListProvider);
  return videosAsync.when(
    data: (videos) => videos.isNotEmpty ? videos.first : null,
    loading: () => null,
    error: (_, __) => null,
  );
});

/// Vidéos en cours de lecture ("Continuer la lecture").
final continueWatchingProvider = Provider.autoDispose<List<VideoModel>>((ref) {
  final videosAsync = ref.watch(videoListProvider);
  return videosAsync.when(
    data: (videos) => videos
        .where((v) => v.watchProgressSeconds > 0 && !v.isCompleted)
        .toList(),
    loading: () => [],
    error: (_, __) => [],
  );
});

/// Top 5 des vidéos les plus regardées (avec grands chiffres stylisés façon Netflix).
final top5VideosProvider = Provider.autoDispose<List<VideoModel>>((ref) {
  final videosAsync = ref.watch(videoListProvider);
  return videosAsync.when(
    data: (videos) {
      final sorted = List<VideoModel>.from(videos);
      sorted.sort((a, b) => b.viewsCount.compareTo(a.viewsCount));
      return sorted.take(5).toList();
    },
    loading: () => [],
    error: (_, __) => [],
  );
});

/// Liste des catégories récupérées depuis l'API.
final categoriesProvider = FutureProvider.autoDispose<List<CategoryModel>>((ref) async {
  final res = await apiClient.dio.get(ApiConstants.categories);
  if (res.statusCode == 200) {
    final List items = res.data ?? [];
    return items.map((e) => CategoryModel.fromJson(e)).toList();
  }
  return [];
});

/// Vidéos filtrées pour une catégorie spécifique (ex: Films, Séries, Action).
final videosByCategoryProvider = Provider.family.autoDispose<List<VideoModel>, String>((ref, category) {
  final videosAsync = ref.watch(videoListProvider);
  return videosAsync.when(
    data: (videos) => videos.where((v) => v.category.toLowerCase() == category.toLowerCase()).toList(),
    loading: () => [],
    error: (_, __) => [],
  );
});

/// Requête de recherche textuelle active.
final searchQueryProvider = StateProvider<String>((ref) => '');

/// Vidéos filtrées par la barre de recherche.
final searchResultsProvider = Provider.autoDispose<List<VideoModel>>((ref) {
  final query = ref.watch(searchQueryProvider).trim().toLowerCase();
  final videosAsync = ref.watch(videoListProvider);

  if (query.isEmpty) return [];

  return videosAsync.when(
    data: (videos) => videos.where((v) {
      final inTitle = v.title.toLowerCase().contains(query);
      final inCategory = v.category.toLowerCase().contains(query);
      final inCaption = (v.caption ?? '').toLowerCase().contains(query);
      return inTitle || inCategory || inCaption;
    }).toList(),
    loading: () => [],
    error: (_, __) => [],
  );
});
