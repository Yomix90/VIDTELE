import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/api_client.dart';
import '../core/constants/api_constants.dart';
import '../models/category_model.dart';
import '../models/home_model.dart';
import '../models/series_detail_model.dart';
import '../models/video_model.dart';

/// Provider pour charger l'intégralité du catalogue vidéo autonome (films, documentaires, hors épisodes de séries).
final videoListProvider = FutureProvider.autoDispose<List<VideoModel>>((ref) async {
  final res = await apiClient.dio.get(
    ApiConstants.videos,
    queryParameters: {'limit': 100, 'exclude_episodes': true},
  );
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

/// Modèle pour les séries dans le slider d'accueil
class SeriesItemModel {
  final int id;
  final String title;
  final String? titleFr;
  final String? titleAr;
  final String? titleEn;
  final String? synopsis;
  final String? posterPath;
  final String? bannerPath;
  final int? year;
  final double? rating;
  final int? firstVideoId;

  SeriesItemModel({
    required this.id,
    required this.title,
    this.titleFr,
    this.titleAr,
    this.titleEn,
    this.synopsis,
    this.posterPath,
    this.bannerPath,
    this.year,
    this.rating,
    this.firstVideoId,
  });

  factory SeriesItemModel.fromJson(Map<String, dynamic> json) {
    return SeriesItemModel(
      id: json['id'] ?? 0,
      title: json['title'] ?? json['title_fr'] ?? 'Série',
      titleFr: json['title_fr'],
      titleAr: json['title_ar'],
      titleEn: json['title_en'],
      synopsis: json['synopsis'],
      posterPath: json['poster_path'],
      bannerPath: json['banner_path'],
      year: json['year'],
      rating: (json['rating'] as num?)?.toDouble(),
      firstVideoId: json['first_video_id'],
    );
  }
}

/// Dernières séries ajoutées pour le carousel/slider d'accueil
final latestSeriesProvider = FutureProvider.autoDispose<List<SeriesItemModel>>((ref) async {
  try {
    final res = await apiClient.dio.get('/api/videos/series/latest');
    if (res.statusCode == 200 && res.data is List) {
      return (res.data as List).map((e) => SeriesItemModel.fromJson(e)).toList();
    }
  } catch (_) {}
  return [];
});

/// Provider pour récupérer la liste de toutes les séries TV publiées.
final seriesListProvider = FutureProvider.autoDispose<List<SeriesDetailModel>>((ref) async {
  try {
    final res = await apiClient.dio.get(ApiConstants.series);
    if (res.statusCode == 200 && res.data is List) {
      return (res.data as List).map((e) => SeriesDetailModel.fromJson(e)).toList();
    }
  } catch (_) {}
  return [];
});

/// Provider pour charger le détail complet d'une série avec ses saisons et épisodes.
final seriesDetailProvider = FutureProvider.family.autoDispose<SeriesDetailModel?, int>((ref, seriesId) async {
  try {
    final res = await apiClient.dio.get(ApiConstants.seriesDetail(seriesId));
    if (res.statusCode == 200 && res.data != null) {
      return SeriesDetailModel.fromJson(res.data);
    }
  } catch (_) {}
  return null;
});

/// Provider principal pour les données complètes de la page d'accueil (/api/home)
final homeDataProvider = FutureProvider.autoDispose<HomeScreenData>((ref) async {
  try {
    final res = await apiClient.dio.get(ApiConstants.home);
    if (res.statusCode == 200 && res.data != null) {
      return HomeScreenData.fromJson(res.data);
    }
  } catch (_) {}
  try {
    final res = await apiClient.dio.get('/api/videos/home');
    if (res.statusCode == 200 && res.data != null) {
      return HomeScreenData.fromJson(res.data);
    }
  } catch (_) {}
  return HomeScreenData();
});

/// Provider pour le Top 5 des séries par lectures des 7 derniers jours (/api/series/top)
final topSeriesProvider = FutureProvider.autoDispose<List<TopSeriesModel>>((ref) async {
  try {
    final res = await apiClient.dio.get(ApiConstants.topSeriesWithParams(period: '7d', limit: 5));
    if (res.statusCode == 200 && res.data is List) {
      return (res.data as List).map((e) => TopSeriesModel.fromJson(e)).toList();
    }
  } catch (_) {}
  return [];
});


