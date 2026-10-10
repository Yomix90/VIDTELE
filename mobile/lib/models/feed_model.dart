/// Modèle représentant un épisode ou vidéo dans le flux vertical TikTok / Reels.
class FeedItemModel {
  final int id;
  final int telegramMessageId;
  final String title;
  final int? seriesId;
  final String? seriesTitle;
  final int seasonNumber;
  final int episodeNumber;
  final String? episodeTitle;
  final String? caption;
  final String category;
  final int durationSeconds;
  final int fileSizeBytes;
  final String mimeType;
  final String? thumbnailPath;
  final int viewsCount;
  final bool isFavorite;
  final double watchProgressSeconds;
  final bool isCompleted;
  final String streamUrl;
  final int? nextEpisodeVideoId;

  FeedItemModel({
    required this.id,
    required this.telegramMessageId,
    required this.title,
    this.seriesId,
    this.seriesTitle,
    this.seasonNumber = 1,
    this.episodeNumber = 1,
    this.episodeTitle,
    this.caption,
    this.category = 'Général',
    this.durationSeconds = 0,
    this.fileSizeBytes = 0,
    this.mimeType = 'video/mp4',
    this.thumbnailPath,
    this.viewsCount = 0,
    this.isFavorite = false,
    this.watchProgressSeconds = 0.0,
    this.isCompleted = false,
    required this.streamUrl,
    this.nextEpisodeVideoId,
  });

  /// Titre d'affichage complet (ex: "La Revanche du PDG · S01E03")
  String get displayHeadline {
    if (seriesTitle != null && seriesTitle!.isNotEmpty) {
      return '$seriesTitle · S${seasonNumber.toString().padLeft(2, '0')}E${episodeNumber.toString().padLeft(2, '0')}';
    }
    return title;
  }

  /// Sous-titre d'épisode
  String get displaySubtitle {
    if (episodeTitle != null && episodeTitle!.isNotEmpty) {
      return episodeTitle!;
    }
    return title;
  }

  factory FeedItemModel.fromJson(Map<String, dynamic> json) {
    return FeedItemModel(
      id: json['id'] ?? json['video_id'] ?? 0,
      telegramMessageId: json['telegram_message_id'] ?? 0,
      title: json['title'] ?? 'Sans titre',
      seriesId: json['series_id'],
      seriesTitle: json['series_title'],
      seasonNumber: json['season_number'] ?? 1,
      episodeNumber: json['episode_number'] ?? 1,
      episodeTitle: json['episode_title'],
      caption: json['caption'],
      category: json['category'] ?? 'Général',
      durationSeconds: json['duration_seconds'] ?? 0,
      fileSizeBytes: json['file_size_bytes'] ?? 0,
      mimeType: json['mime_type'] ?? 'video/mp4',
      thumbnailPath: json['thumbnail_path'],
      viewsCount: json['views_count'] ?? 0,
      isFavorite: json['is_favorite'] ?? false,
      watchProgressSeconds: (json['watch_progress_seconds'] as num?)?.toDouble() ?? 0.0,
      isCompleted: json['is_completed'] ?? false,
      streamUrl: json['stream_url'] ?? '',
      nextEpisodeVideoId: json['next_episode_video_id'],
    );
  }

  FeedItemModel copyWith({
    bool? isFavorite,
    double? watchProgressSeconds,
    bool? isCompleted,
    int? viewsCount,
  }) {
    return FeedItemModel(
      id: id,
      telegramMessageId: telegramMessageId,
      title: title,
      seriesId: seriesId,
      seriesTitle: seriesTitle,
      seasonNumber: seasonNumber,
      episodeNumber: episodeNumber,
      episodeTitle: episodeTitle,
      caption: caption,
      category: category,
      durationSeconds: durationSeconds,
      fileSizeBytes: fileSizeBytes,
      mimeType: mimeType,
      thumbnailPath: thumbnailPath,
      viewsCount: viewsCount ?? this.viewsCount,
      isFavorite: isFavorite ?? this.isFavorite,
      watchProgressSeconds: watchProgressSeconds ?? this.watchProgressSeconds,
      isCompleted: isCompleted ?? this.isCompleted,
      streamUrl: streamUrl,
      nextEpisodeVideoId: nextEpisodeVideoId,
    );
  }
}

/// Réponse paginée du flux vertical
class FeedResponseModel {
  final List<FeedItemModel> items;
  final int? nextCursor;
  final bool hasMore;

  FeedResponseModel({
    required this.items,
    this.nextCursor,
    this.hasMore = false,
  });

  factory FeedResponseModel.fromJson(Map<String, dynamic> json) {
    final list = json['items'] as List? ?? [];
    return FeedResponseModel(
      items: list.map((e) => FeedItemModel.fromJson(e)).toList(),
      nextCursor: json['next_cursor'],
      hasMore: json['has_more'] ?? false,
    );
  }
}
