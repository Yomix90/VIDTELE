import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vidtele_mobile/core/services/video_player_manager.dart';
import 'package:vidtele_mobile/models/feed_model.dart';
import 'package:vidtele_mobile/providers/feed_provider.dart';
import 'package:vidtele_mobile/screens/player/reels_screen.dart';

class FakeFeedNotifier extends StateNotifier<FeedState> implements FeedNotifier {
  FakeFeedNotifier() : super(const FeedState());

  @override
  int? get seriesId => null;

  @override
  Ref get ref => throw UnimplementedError();

  @override
  Future<void> loadInitial() async {}

  @override
  Future<void> loadMore() async {}

  @override
  void toggleFavorite(int videoId) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Reels Feed Models & Widgets Tests', () {
    test('FeedItemModel parses correctly with series and binge information', () {
      final json = {
        'id': 42,
        'telegram_message_id': 1042,
        'title': 'Le Secret Révélé',
        'series_id': 5,
        'series_title': 'Destins Croisés',
        'season_number': 1,
        'episode_number': 4,
        'episode_title': 'Le Secret Révélé',
        'caption': 'Un secret bouleversant éclate au grand jour.',
        'category': 'Drame',
        'duration_seconds': 180,
        'file_size_bytes': 15000000,
        'mime_type': 'video/mp4',
        'thumbnail_path': '/thumbs/ep4.jpg',
        'views_count': 320,
        'is_favorite': true,
        'watch_progress_seconds': 45.0,
        'is_completed': false,
        'stream_url': '/api/videos/42/stream',
        'next_episode_video_id': 43,
      };

      final item = FeedItemModel.fromJson(json);

      expect(item.id, 42);
      expect(item.displayHeadline, 'Destins Croisés · S01E04');
      expect(item.displaySubtitle, 'Le Secret Révélé');
      expect(item.nextEpisodeVideoId, 43);
      expect(item.isFavorite, isTrue);
      expect(item.watchProgressSeconds, 45.0);
    });

    test('FeedResponseModel parses cursor pagination', () {
      final json = {
        'items': [
          {
            'id': 100,
            'telegram_message_id': 1100,
            'title': 'Clip 1',
            'stream_url': '/api/videos/100/stream',
          },
          {
            'id': 99,
            'telegram_message_id': 1099,
            'title': 'Clip 2',
            'stream_url': '/api/videos/99/stream',
          }
        ],
        'next_cursor': 99,
        'has_more': true,
      };

      final res = FeedResponseModel.fromJson(json);

      expect(res.items.length, 2);
      expect(res.nextCursor, 99);
      expect(res.hasMore, isTrue);
    });

    testWidgets('ReelsScreen pauses immediately when isActive becomes false', (tester) async {
      final manager = VideoPlayerManager();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            videoPlayerManagerProvider.overrideWithValue(manager),
            feedNotifierProvider.overrideWith((ref) => FakeFeedNotifier()),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: ReelsScreen(isActive: true),
            ),
          ),
        ),
      );

      await tester.pump();

      // Changer isActive à false
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            videoPlayerManagerProvider.overrideWithValue(manager),
            feedNotifierProvider.overrideWith((ref) => FakeFeedNotifier()),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: ReelsScreen(isActive: false),
            ),
          ),
        ),
      );

      await tester.pump();

      // Vérifier qu'aucun player n'est en train de jouer
      expect(manager.activePlayerId, isNull);

      // Nettoyer l'arbre de widgets
      await tester.pumpWidget(const SizedBox());
    });
  });
}
