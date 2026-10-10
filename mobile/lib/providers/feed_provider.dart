import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/api_client.dart';
import '../core/constants/api_constants.dart';
import '../models/feed_model.dart';
import '../models/video_model.dart';
import 'video_provider.dart';

/// État du flux vertical d'épisodes et de vidéos
class FeedState {
  final List<FeedItemModel> items;
  final bool isLoading;
  final bool isLoadingMore;
  final int? nextCursor;
  final bool hasMore;
  final String? error;

  const FeedState({
    this.items = const [],
    this.isLoading = false,
    this.isLoadingMore = false,
    this.nextCursor,
    this.hasMore = false,
    this.error,
  });

  FeedState copyWith({
    List<FeedItemModel>? items,
    bool? isLoading,
    bool? isLoadingMore,
    int? nextCursor,
    bool? hasMore,
    String? error,
  }) {
    return FeedState(
      items: items ?? this.items,
      isLoading: isLoading ?? this.isLoading,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      nextCursor: nextCursor ?? this.nextCursor,
      hasMore: hasMore ?? this.hasMore,
      error: error,
    );
  }
}

/// Notifier gérant le flux TikTok d'épisodes avec pagination par curseur
class FeedNotifier extends StateNotifier<FeedState> {
  final int? seriesId;
  final Ref ref;

  FeedNotifier({this.seriesId, required this.ref}) : super(const FeedState()) {
    loadInitial();
  }

  Future<void> loadInitial() async {
    state = state.copyWith(isLoading: true, error: null);

    try {
      final queryParams = <String, dynamic>{
        'limit': 15,
        if (seriesId != null) 'series_id': seriesId,
      };

      final res = await apiClient.dio.get(
        ApiConstants.feed,
        queryParameters: queryParams,
      );

      if (res.statusCode == 200 && res.data != null) {
        final parsed = FeedResponseModel.fromJson(res.data);
        state = state.copyWith(
          items: parsed.items,
          nextCursor: parsed.nextCursor,
          hasMore: parsed.hasMore,
          isLoading: false,
        );
        return;
      }
    } catch (_) {
      // Fallback si l'endpoint racine échoue : tenter avec /api/videos
      try {
        final videos = await ref.read(videoListProvider.future);
        final converted = videos.map((v) => _videoToFeedItem(v)).toList();
        state = state.copyWith(
          items: converted,
          hasMore: false,
          isLoading: false,
        );
        return;
      } catch (e) {
        state = state.copyWith(
          isLoading: false,
          error: 'Impossible de charger le flux vidéo.',
        );
      }
    }
  }

  Future<void> loadMore() async {
    if (state.isLoadingMore || !state.hasMore || state.nextCursor == null) return;

    state = state.copyWith(isLoadingMore: true);

    try {
      final queryParams = <String, dynamic>{
        'limit': 15,
        'cursor': state.nextCursor,
        if (seriesId != null) 'series_id': seriesId,
      };

      final res = await apiClient.dio.get(
        ApiConstants.feed,
        queryParameters: queryParams,
      );

      if (res.statusCode == 200 && res.data != null) {
        final parsed = FeedResponseModel.fromJson(res.data);
        final existingIds = state.items.map((e) => e.id).toSet();
        final newItems = parsed.items.where((e) => !existingIds.contains(e.id)).toList();

        state = state.copyWith(
          items: [...state.items, ...newItems],
          nextCursor: parsed.nextCursor,
          hasMore: parsed.hasMore,
          isLoadingMore: false,
        );
      } else {
        state = state.copyWith(isLoadingMore: false);
      }
    } catch (_) {
      state = state.copyWith(isLoadingMore: false);
    }
  }

  void toggleFavorite(int videoId) {
    state = state.copyWith(
      items: state.items.map((item) {
        if (item.id == videoId) {
          return item.copyWith(isFavorite: !item.isFavorite);
        }
        return item;
      }).toList(),
    );
  }

  static FeedItemModel _videoToFeedItem(VideoModel v) {
    return FeedItemModel(
      id: v.id,
      telegramMessageId: v.telegramMessageId,
      title: v.title,
      seasonNumber: v.seasonNumber ?? 1,
      episodeNumber: v.episodeNumber ?? 1,
      episodeTitle: v.episodeTitle,
      caption: v.caption,
      category: v.category,
      durationSeconds: v.durationSeconds,
      fileSizeBytes: v.fileSizeBytes,
      mimeType: v.mimeType,
      thumbnailPath: v.thumbnailPath,
      viewsCount: v.viewsCount,
      isFavorite: v.isFavorite,
      watchProgressSeconds: v.watchProgressSeconds,
      isCompleted: v.isCompleted,
      streamUrl: ApiConstants.videoStream(v.id),
    );
  }
}

/// Provider pour le flux TikTok principal
final feedNotifierProvider = StateNotifierProvider.autoDispose<FeedNotifier, FeedState>((ref) {
  return FeedNotifier(ref: ref);
});

/// Provider familial pour binger une série spécifique dans le feed vertical
final seriesFeedNotifierProvider = StateNotifierProvider.autoDispose.family<FeedNotifier, FeedState, int>((ref, seriesId) {
  return FeedNotifier(seriesId: seriesId, ref: ref);
});
