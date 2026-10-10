import 'video_model.dart';

/// Item pour le slider Hero de l'accueil
class HomeHeroItem {
  final int id;
  final String title;
  final String? titleFr;
  final String? titleAr;
  final String? titleEn;
  final String synopsis;
  final String? posterPath;
  final String? bannerPath;
  final int? year;
  final double? rating;
  final String category;
  final int episodesCount;
  final int? firstVideoId;

  HomeHeroItem({
    required this.id,
    required this.title,
    this.titleFr,
    this.titleAr,
    this.titleEn,
    this.synopsis = '',
    this.posterPath,
    this.bannerPath,
    this.year,
    this.rating,
    this.category = 'Série',
    this.episodesCount = 0,
    this.firstVideoId,
  });

  factory HomeHeroItem.fromJson(Map<String, dynamic> json) {
    return HomeHeroItem(
      id: json['id'] ?? 0,
      title: json['title'] ?? json['title_fr'] ?? 'Sans titre',
      titleFr: json['title_fr'],
      titleAr: json['title_ar'],
      titleEn: json['title_en'],
      synopsis: json['synopsis'] ?? '',
      posterPath: json['poster_path'],
      bannerPath: json['banner_path'] ?? json['poster_path'],
      year: json['year'],
      rating: (json['rating'] as num?)?.toDouble(),
      category: json['category'] ?? 'Série',
      episodesCount: json['episodes_count'] ?? 0,
      firstVideoId: json['first_video_id'],
    );
  }
}

/// Item pour le Top 5 des séries
class TopSeriesModel {
  final int id;
  final int rank;
  final String title;
  final String? titleFr;
  final String? titleAr;
  final String? titleEn;
  final String synopsis;
  final String? posterPath;
  final String? bannerPath;
  final int? year;
  final double? rating;
  final int seasonsCount;
  final int episodesCount;
  final int viewsLast7d;
  final int? firstVideoId;

  TopSeriesModel({
    required this.id,
    required this.rank,
    required this.title,
    this.titleFr,
    this.titleAr,
    this.titleEn,
    this.synopsis = '',
    this.posterPath,
    this.bannerPath,
    this.year,
    this.rating,
    this.seasonsCount = 0,
    this.episodesCount = 0,
    this.viewsLast7d = 0,
    this.firstVideoId,
  });

  factory TopSeriesModel.fromJson(Map<String, dynamic> json) {
    return TopSeriesModel(
      id: json['id'] ?? 0,
      rank: json['rank'] ?? 1,
      title: json['title'] ?? json['title_fr'] ?? 'Série',
      titleFr: json['title_fr'],
      titleAr: json['title_ar'],
      titleEn: json['title_en'],
      synopsis: json['synopsis'] ?? '',
      posterPath: json['poster_path'],
      bannerPath: json['banner_path'] ?? json['poster_path'],
      year: json['year'],
      rating: (json['rating'] as num?)?.toDouble(),
      seasonsCount: json['seasons_count'] ?? 0,
      episodesCount: json['episodes_count'] ?? 0,
      viewsLast7d: json['views_last_7d'] ?? 0,
      firstVideoId: json['first_video_id'],
    );
  }
}

/// Section de genre sur la page d'accueil
class HomeGenreSection {
  final String name;
  final int count;
  final List<VideoModel> items;

  HomeGenreSection({
    required this.name,
    this.count = 0,
    required this.items,
  });

  factory HomeGenreSection.fromJson(Map<String, dynamic> json) {
    final list = json['items'] as List? ?? [];
    return HomeGenreSection(
      name: json['name'] ?? '',
      count: json['count'] ?? list.length,
      items: list.map((e) => VideoModel.fromJson(e)).toList(),
    );
  }
}

/// Modèle global pour la page d'accueil (/api/home)
class HomeScreenData {
  final List<HomeHeroItem> hero;
  final List<TopSeriesModel> top5;
  final List<VideoModel> continueWatching;
  final List<VideoModel> newReleases;
  final List<VideoModel> trending;
  final List<HomeGenreSection> genres;

  HomeScreenData({
    this.hero = const [],
    this.top5 = const [],
    this.continueWatching = const [],
    this.newReleases = const [],
    this.trending = const [],
    this.genres = const [],
  });

  factory HomeScreenData.fromJson(Map<String, dynamic> json) {
    final heroList = (json['hero'] as List? ?? [])
        .map((e) => HomeHeroItem.fromJson(e))
        .toList();
    final top5List = (json['top5'] as List? ?? [])
        .map((e) => TopSeriesModel.fromJson(e))
        .toList();
    final cwList = (json['continue_watching'] as List? ?? [])
        .map((e) => VideoModel.fromJson(e))
        .toList();
    final newList = ((json['new_releases'] ?? json['new']) as List? ?? [])
        .map((e) => VideoModel.fromJson(e))
        .toList();
    final trendingList = (json['trending'] as List? ?? [])
        .map((e) => VideoModel.fromJson(e))
        .toList();
    final genresList = (json['genres'] as List? ?? [])
        .map((e) => HomeGenreSection.fromJson(e))
        .toList();

    return HomeScreenData(
      hero: heroList,
      top5: top5List,
      continueWatching: cwList,
      newReleases: newList,
      trending: trendingList,
      genres: genresList,
    );
  }
}
