import 'video_model.dart';

/// Modèle pour un épisode avec support de la localisation, de la progression et de l'objet vidéo.
class EpisodeModel {
  final int id;
  final int seasonId;
  final int seasonNumber;
  final int number;
  final String? titleFr;
  final String? titleAr;
  final String? titleEn;
  final String? synopsisFr;
  final String? synopsisAr;
  final String? synopsisEn;
  final int durationSec;
  final String? thumbnailPath;
  final int? telegramVideoId;
  final VideoModel? video;
  final double watchProgressSeconds;
  final bool isCompleted;

  EpisodeModel({
    required this.id,
    required this.seasonId,
    required this.seasonNumber,
    required this.number,
    this.titleFr,
    this.titleAr,
    this.titleEn,
    this.synopsisFr,
    this.synopsisAr,
    this.synopsisEn,
    required this.durationSec,
    this.thumbnailPath,
    this.telegramVideoId,
    this.video,
    required this.watchProgressSeconds,
    required this.isCompleted,
  });

  /// Titre adapté selon le code de langue
  String getLocalizedTitle(String langCode) {
    if (langCode == 'ar' && titleAr != null && titleAr!.trim().isNotEmpty) {
      return titleAr!;
    }
    if (langCode == 'en' && titleEn != null && titleEn!.trim().isNotEmpty) {
      return titleEn!;
    }
    return titleFr ?? (langCode == 'ar' ? 'الحلقة $number' : 'Épisode $number');
  }

  /// Synopsis adapté selon la langue
  String? getLocalizedSynopsis(String langCode) {
    if (langCode == 'ar' && synopsisAr != null && synopsisAr!.trim().isNotEmpty) {
      return synopsisAr;
    }
    if (langCode == 'en' && synopsisEn != null && synopsisEn!.trim().isNotEmpty) {
      return synopsisEn;
    }
    return synopsisFr;
  }

  /// Pourcentage de visionnage
  double get progressFraction {
    if (durationSec <= 0) return 0.0;
    return (watchProgressSeconds / durationSec).clamp(0.0, 1.0);
  }

  /// Durée formatée (ex: "45 min")
  String get formattedDuration {
    if (durationSec <= 0) return '--';
    final mins = durationSec ~/ 60;
    if (mins >= 60) {
      final hours = mins ~/ 60;
      final remMins = mins % 60;
      return '${hours}h ${remMins}m';
    }
    return '$mins min';
  }

  factory EpisodeModel.fromJson(Map<String, dynamic> json) {
    return EpisodeModel(
      id: json['id'] ?? 0,
      seasonId: json['season_id'] ?? 0,
      seasonNumber: json['season_number'] ?? 1,
      number: json['number'] ?? 1,
      titleFr: json['title_fr'],
      titleAr: json['title_ar'],
      titleEn: json['title_en'],
      synopsisFr: json['synopsis_fr'],
      synopsisAr: json['synopsis_ar'],
      synopsisEn: json['synopsis_en'],
      durationSec: json['duration_sec'] ?? 0,
      thumbnailPath: json['thumbnail_path'],
      telegramVideoId: json['telegram_video_id'],
      video: json['video'] != null ? VideoModel.fromJson(json['video']) : null,
      watchProgressSeconds: (json['watch_progress_seconds'] as num?)?.toDouble() ?? 0.0,
      isCompleted: json['is_completed'] ?? false,
    );
  }
}

/// Modèle pour une saison
class SeasonModel {
  final int id;
  final int number;
  final String? titleFr;
  final String? titleAr;
  final String? posterPath;
  final int episodeCount;
  final List<EpisodeModel> episodes;

  SeasonModel({
    required this.id,
    required this.number,
    this.titleFr,
    this.titleAr,
    this.posterPath,
    required this.episodeCount,
    required this.episodes,
  });

  String getLocalizedTitle(String langCode) {
    if (langCode == 'ar') {
      return titleAr ?? 'الموسم $number';
    }
    return titleFr ?? 'Saison $number';
  }

  factory SeasonModel.fromJson(Map<String, dynamic> json) {
    final epList = (json['episodes'] as List? ?? [])
        .map((e) => EpisodeModel.fromJson(e))
        .toList();

    return SeasonModel(
      id: json['id'] ?? 0,
      number: json['number'] ?? 1,
      titleFr: json['title_fr'],
      titleAr: json['title_ar'],
      posterPath: json['poster_path'],
      episodeCount: json['episode_count'] ?? epList.length,
      episodes: epList,
    );
  }
}

/// Modèle d'une série similaire ou recommandée
class SimilarSeriesModel {
  final int id;
  final String titleFr;
  final String? titleAr;
  final String? titleEn;
  final String? posterPath;
  final String? bannerPath;
  final double? rating;
  final int? yearStart;
  final int episodesCount;

  SimilarSeriesModel({
    required this.id,
    required this.titleFr,
    this.titleAr,
    this.titleEn,
    this.posterPath,
    this.bannerPath,
    this.rating,
    this.yearStart,
    required this.episodesCount,
  });

  String getLocalizedTitle(String langCode) {
    if (langCode == 'ar' && titleAr != null && titleAr!.trim().isNotEmpty) {
      return titleAr!;
    }
    if (langCode == 'en' && titleEn != null && titleEn!.trim().isNotEmpty) {
      return titleEn!;
    }
    return titleFr;
  }

  factory SimilarSeriesModel.fromJson(Map<String, dynamic> json) {
    return SimilarSeriesModel(
      id: json['id'] ?? 0,
      titleFr: json['title_fr'] ?? 'Série',
      titleAr: json['title_ar'],
      titleEn: json['title_en'],
      posterPath: json['poster_path'],
      bannerPath: json['banner_path'],
      rating: (json['rating'] as num?)?.toDouble(),
      yearStart: json['year_start'],
      episodesCount: json['episodes_count'] ?? 0,
    );
  }
}

/// Modèle complet de détail d'une série
class SeriesDetailModel {
  final int id;
  final String slug;
  final String titleFr;
  final String? titleAr;
  final String? titleEn;
  final String? synopsisFr;
  final String? synopsisAr;
  final String? synopsisEn;
  final int? yearStart;
  final double? rating;
  final String status;
  final String? posterPath;
  final String? bannerPath;
  final int seasonsCount;
  final int episodesCount;
  final int? lastWatchedEpisodeId;
  final List<String> genres;
  final bool isFavorite;
  final List<SimilarSeriesModel> similarSeries;
  final List<SeasonModel> seasons;

  SeriesDetailModel({
    required this.id,
    required this.slug,
    required this.titleFr,
    this.titleAr,
    this.titleEn,
    this.synopsisFr,
    this.synopsisAr,
    this.synopsisEn,
    this.yearStart,
    this.rating,
    required this.status,
    this.posterPath,
    this.bannerPath,
    required this.seasonsCount,
    required this.episodesCount,
    this.lastWatchedEpisodeId,
    this.genres = const [],
    this.isFavorite = false,
    this.similarSeries = const [],
    required this.seasons,
  });

  String getLocalizedTitle(String langCode) {
    if (langCode == 'ar' && titleAr != null && titleAr!.trim().isNotEmpty) {
      return titleAr!;
    }
    if (langCode == 'en' && titleEn != null && titleEn!.trim().isNotEmpty) {
      return titleEn!;
    }
    return titleFr;
  }

  String? getLocalizedSynopsis(String langCode) {
    if (langCode == 'ar' && synopsisAr != null && synopsisAr!.trim().isNotEmpty) {
      return synopsisAr;
    }
    if (langCode == 'en' && synopsisEn != null && synopsisEn!.trim().isNotEmpty) {
      return synopsisEn;
    }
    return synopsisFr;
  }

  SeriesDetailModel copyWith({
    bool? isFavorite,
    int? lastWatchedEpisodeId,
  }) {
    return SeriesDetailModel(
      id: id,
      slug: slug,
      titleFr: titleFr,
      titleAr: titleAr,
      titleEn: titleEn,
      synopsisFr: synopsisFr,
      synopsisAr: synopsisAr,
      synopsisEn: synopsisEn,
      yearStart: yearStart,
      rating: rating,
      status: status,
      posterPath: posterPath,
      bannerPath: bannerPath,
      seasonsCount: seasonsCount,
      episodesCount: episodesCount,
      lastWatchedEpisodeId: lastWatchedEpisodeId ?? this.lastWatchedEpisodeId,
      genres: genres,
      isFavorite: isFavorite ?? this.isFavorite,
      similarSeries: similarSeries,
      seasons: seasons,
    );
  }

  factory SeriesDetailModel.fromJson(Map<String, dynamic> json) {
    final sList = (json['seasons'] as List? ?? [])
        .map((e) => SeasonModel.fromJson(e))
        .toList();

    final simList = (json['similar_series'] as List? ?? [])
        .map((e) => SimilarSeriesModel.fromJson(e))
        .toList();

    final gList = (json['genres'] as List? ?? [])
        .map((e) => e.toString())
        .toList();

    return SeriesDetailModel(
      id: json['id'] ?? 0,
      slug: json['slug'] ?? '',
      titleFr: json['title_fr'] ?? 'Série',
      titleAr: json['title_ar'],
      titleEn: json['title_en'],
      synopsisFr: json['synopsis_fr'],
      synopsisAr: json['synopsis_ar'],
      synopsisEn: json['synopsis_en'],
      yearStart: json['year_start'],
      rating: (json['rating'] as num?)?.toDouble(),
      status: json['status'] ?? 'ongoing',
      posterPath: json['poster_path'],
      bannerPath: json['banner_path'],
      seasonsCount: json['seasons_count'] ?? sList.length,
      episodesCount: json['episodes_count'] ?? 0,
      lastWatchedEpisodeId: json['last_watched_episode_id'],
      genres: gList.isNotEmpty ? gList : const ['Micro-série', 'Drame'],
      isFavorite: json['is_favorite'] ?? false,
      similarSeries: simList,
      seasons: sList,
    );
  }
}
