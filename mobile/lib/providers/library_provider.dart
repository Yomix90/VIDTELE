import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import '../core/api/api_client.dart';
import '../core/constants/api_constants.dart';
import '../models/video_model.dart';
import 'video_provider.dart';

/// Gestionnaire d'état pour la liste des favoris de l'utilisateur
class FavoritesNotifier extends StateNotifier<AsyncValue<List<VideoModel>>> {
  final Ref ref;

  FavoritesNotifier(this.ref) : super(const AsyncValue.loading()) {
    fetchFavorites();
  }

  /// Récupère la liste des vidéos favorites depuis le serveur
  Future<void> fetchFavorites() async {
    state = const AsyncValue.loading();
    try {
      final response = await apiClient.dio.get(ApiConstants.favorites);
      final List<dynamic> data = response.data;
      final favorites = data.map((item) {
        if (item is Map<String, dynamic> && item['video'] != null) {
          return VideoModel.fromJson(item['video']);
        }
        return VideoModel.fromJson(item);
      }).toList();
      state = AsyncValue.data(favorites);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// Ajoute ou retire une vidéo des favoris et synchronise le catalogue
  Future<bool> toggleFavorite(VideoModel video) async {
    final currentList = state.value ?? [];
    final isFav = currentList.any((v) => v.id == video.id);

    // Mise à jour optimiste locale
    if (isFav) {
      state = AsyncValue.data(currentList.where((v) => v.id != video.id).toList());
    } else {
      state = AsyncValue.data([...currentList, video.copyWith(isFavorite: true)]);
    }

    try {
      if (isFav) {
        await apiClient.dio.delete(ApiConstants.favoriteAction(video.id));
      } else {
        await apiClient.dio.post(ApiConstants.favoriteAction(video.id));
      }
      // Rafraîchir également la liste globale des vidéos pour synchroniser les cœurs
      ref.invalidate(videoListProvider);
      return !isFav;
    } catch (e) {
      // Annulation en cas d'erreur réseau
      state = AsyncValue.data(currentList);
      return isFav;
    }
  }
}

final favoritesProvider =
    StateNotifierProvider<FavoritesNotifier, AsyncValue<List<VideoModel>>>((ref) {
  return FavoritesNotifier(ref);
});

/// Élément de l'historique de visionnage
class HistoryItem {
  final VideoModel video;
  final double progressSeconds;
  final double lastPositionSeconds;
  final bool isCompleted;
  final DateTime updatedAt;

  HistoryItem({
    required this.video,
    required this.progressSeconds,
    required this.lastPositionSeconds,
    required this.isCompleted,
    required this.updatedAt,
  });

  factory HistoryItem.fromJson(Map<String, dynamic> json) {
    final VideoModel vid = json['video'] != null && json['video'] is Map<String, dynamic>
        ? VideoModel.fromJson(json['video'])
        : VideoModel.fromJson(json);

    final double lastPos = (json['last_position_seconds'] as num?)?.toDouble() ??
        (json['position_seconds'] as num?)?.toDouble() ??
        (json['progress_seconds'] as num?)?.toDouble() ??
        0.0;
    final double progSec = (json['progress_seconds'] as num?)?.toDouble() ??
        (json['position_seconds'] as num?)?.toDouble() ??
        lastPos;
    final bool comp = json['is_completed'] ?? json['completed'] ?? false;

    return HistoryItem(
      video: vid,
      progressSeconds: progSec,
      lastPositionSeconds: lastPos,
      isCompleted: comp,
      updatedAt: DateTime.tryParse(json['updated_at'] ?? json['last_watched_at'] ?? '') ?? DateTime.now(),
    );
  }

  double get progressFraction {
    if (video.durationSeconds <= 0) return 0.0;
    return (lastPositionSeconds / video.durationSeconds).clamp(0.0, 1.0);
  }
}

/// Gestionnaire d'état pour l'historique de visionnage
class HistoryNotifier extends StateNotifier<AsyncValue<List<HistoryItem>>> {
  final Ref ref;

  HistoryNotifier(this.ref) : super(const AsyncValue.loading()) {
    fetchHistory();
  }

  Future<void> fetchHistory() async {
    state = const AsyncValue.loading();
    try {
      final response = await apiClient.dio.get(ApiConstants.history);
      final List<dynamic> data = response.data;
      final history = data.map((item) => HistoryItem.fromJson(item)).toList();
      state = AsyncValue.data(history);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  /// Met à jour la progression de lecture sur le backend et rafraîchit localement
  Future<void> updateProgress(int videoId, double progressSeconds, bool completed) async {
    try {
      await apiClient.dio.put(
        ApiConstants.videoProgress(videoId),
        data: {
          'position_seconds': progressSeconds,
          'progress_seconds': progressSeconds,
          'completed': completed,
        },
      );
      // Rafraîchir les listes
      fetchHistory();
      ref.invalidate(videoListProvider);
    } catch (_) {}
  }
}

final historyProvider =
    StateNotifierProvider<HistoryNotifier, AsyncValue<List<HistoryItem>>>((ref) {
  return HistoryNotifier(ref);
});
