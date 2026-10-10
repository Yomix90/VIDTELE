/// Modèle représentant une vidéo du catalogue VidTele avec ses métadonnées de lecture.
class VideoModel {
  final int id;
  final int telegramMessageId;
  final String title;
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
  final int? seasonNumber;
  final int? episodeNumber;
  final String? episodeTitle;
  final String? fileName;
  final DateTime? telegramDate;
  final bool isPublished;

  VideoModel({
    required this.id,
    required this.telegramMessageId,
    required this.title,
    this.caption,
    required this.category,
    required this.durationSeconds,
    required this.fileSizeBytes,
    required this.mimeType,
    this.thumbnailPath,
    required this.viewsCount,
    required this.isFavorite,
    required this.watchProgressSeconds,
    required this.isCompleted,
    this.seasonNumber,
    this.episodeNumber,
    this.episodeTitle,
    this.fileName,
    this.telegramDate,
    this.isPublished = true,
  });

  /// Durée formatée par défaut (ex: "1h 12m" ou "3m 45s")
  String get formattedDuration {
    if (durationSeconds <= 0) return 'Court clip';
    final minutes = durationSeconds ~/ 60;
    final seconds = durationSeconds % 60;
    if (minutes >= 60) {
      final hours = minutes ~/ 60;
      final remMinutes = minutes % 60;
      return '${hours}h ${remMinutes}m';
    }
    return '${minutes}m ${seconds}s';
  }

  /// Durée formatée selon la langue (FR, EN, AR)
  String formattedDurationWithLocale(String langCode) {
    if (durationSeconds <= 0) {
      if (langCode == 'ar') return 'مقطع قصير';
      if (langCode == 'en') return 'Short clip';
      return 'Court clip';
    }
    final minutes = durationSeconds ~/ 60;
    final seconds = durationSeconds % 60;
    if (minutes >= 60) {
      final hours = minutes ~/ 60;
      final remMinutes = minutes % 60;
      if (langCode == 'ar') return '$hours س $remMinutes د';
      return '${hours}h ${remMinutes}m';
    }
    if (langCode == 'ar') return '$minutes د $seconds ث';
    return '${minutes}m ${seconds}s';
  }

  /// Pourcentage de visionnage pour la barre de progression (entre 0.0 et 1.0)
  double get progressFraction {
    if (durationSeconds <= 0) return 0.0;
    final fraction = watchProgressSeconds / durationSeconds;
    return fraction.clamp(0.0, 1.0);
  }

  /// Taille du fichier en Mo
  String get formattedFileSize {
    final mb = fileSizeBytes / (1024 * 1024);
    return '${mb.toStringAsFixed(1)} Mo';
  }

  factory VideoModel.fromJson(Map<String, dynamic> json) {
    return VideoModel(
      id: json['id'] ?? json['video_id'] ?? 0,
      telegramMessageId: json['telegram_message_id'] ?? 0,
      title: json['title'] ?? json['video_title'] ?? 'Sans titre',
      caption: json['caption'],
      category: json['category'] ?? 'Général',
      durationSeconds: json['duration_seconds'] ?? 0,
      fileSizeBytes: json['file_size_bytes'] ?? 0,
      mimeType: json['mime_type'] ?? 'video/mp4',
      thumbnailPath: json['thumbnail_path'] ?? json['video_thumbnail'],
      viewsCount: json['views_count'] ?? 0,
      isFavorite: json['is_favorite'] ?? false,
      watchProgressSeconds: (json['watch_progress_seconds'] as num?)?.toDouble() ??
          (json['position_seconds'] as num?)?.toDouble() ??
          0.0,
      isCompleted: json['is_completed'] ?? json['completed'] ?? false,
      seasonNumber: json['season_number'],
      episodeNumber: json['episode_number'],
      episodeTitle: json['episode_title'],
      fileName: json['file_name'],
      telegramDate: json['telegram_date'] != null ? DateTime.tryParse(json['telegram_date']) : null,
      isPublished: json['is_published'] ?? true,
    );
  }

  VideoModel copyWith({
    bool? isFavorite,
    double? watchProgressSeconds,
    bool? isCompleted,
    int? viewsCount,
    int? seasonNumber,
    int? episodeNumber,
    String? episodeTitle,
  }) {
    return VideoModel(
      id: id,
      telegramMessageId: telegramMessageId,
      title: title,
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
      seasonNumber: seasonNumber ?? this.seasonNumber,
      episodeNumber: episodeNumber ?? this.episodeNumber,
      episodeTitle: episodeTitle ?? this.episodeTitle,
      fileName: fileName,
      telegramDate: telegramDate,
      isPublished: isPublished,
    );
  }
}
