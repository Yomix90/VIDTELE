import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vidtele_mobile/models/series_detail_model.dart';
import 'package:vidtele_mobile/providers/video_provider.dart';
import 'package:vidtele_mobile/screens/series/series_detail_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('SeriesDetail & SimilarSeries Model Tests', () {
    test('SeriesDetailModel parses complete response with similar series and genres', () {
      final json = {
        'id': 1,
        'slug': 'destins-croises',
        'title_fr': 'Destins Croisés',
        'title_ar': 'أقدار متقاطعة',
        'title_en': 'Crossed Destinies',
        'synopsis_fr': 'Une romance intense au cœur de la ville moderne.',
        'year_start': 2024,
        'rating': 4.8,
        'status': 'ongoing',
        'poster_path': '/posters/destins.jpg',
        'banner_path': '/banners/destins_wide.jpg',
        'seasons_count': 1,
        'episodes_count': 12,
        'last_watched_episode_id': 2,
        'genres': ['Drame', 'Romance'],
        'is_favorite': true,
        'similar_series': [
          {
            'id': 2,
            'title_fr': 'Le Clan Shelby',
            'title_ar': 'عائلة شيلبي',
            'poster_path': '/posters/shelby.jpg',
            'rating': 4.9,
            'year_start': 2023,
            'episodes_count': 6,
          },
        ],
        'seasons': [
          {
            'id': 10,
            'number': 1,
            'title_fr': 'Saison 1',
            'episode_count': 1,
            'episodes': [
              {
                'id': 101,
                'season_id': 10,
                'season_number': 1,
                'number': 1,
                'title_fr': 'La Rencontre',
                'duration_sec': 180,
                'thumbnail_path': '/thumbs/ep1.jpg',
                'watch_progress_seconds': 90.0,
                'is_completed': false,
              },
            ],
          },
        ],
      };

      final model = SeriesDetailModel.fromJson(json);

      expect(model.id, 1);
      expect(model.titleFr, 'Destins Croisés');
      expect(model.getLocalizedTitle('ar'), 'أقدار متقاطعة');
      expect(model.isFavorite, isTrue);
      expect(model.genres, contains('Romance'));
      expect(model.similarSeries.length, 1);
      expect(model.similarSeries.first.titleFr, 'Le Clan Shelby');
      expect(model.seasons.length, 1);
      expect(model.seasons.first.episodes.length, 1);

      final ep = model.seasons.first.episodes.first;
      expect(ep.progressFraction, 0.5);
      expect(ep.formattedDuration, '3 min');
    });

    testWidgets('SeriesDetailScreen renders with series details', (tester) async {
      final mockSeries = SeriesDetailModel(
        id: 1,
        slug: 'destins-croises',
        titleFr: 'Destins Croisés',
        titleAr: 'أقدار متقاطعة',
        synopsisFr: 'Une romance intense.',
        rating: 4.8,
        yearStart: 2024,
        status: 'ongoing',
        seasonsCount: 1,
        episodesCount: 1,
        genres: const ['Drame', 'Romance'],
        isFavorite: false,
        seasons: [
          SeasonModel(
            id: 10,
            number: 1,
            titleFr: 'Saison 1',
            episodeCount: 1,
            episodes: [
              EpisodeModel(
                id: 101,
                seasonId: 10,
                seasonNumber: 1,
                number: 1,
                titleFr: 'La Rencontre',
                durationSec: 180,
                watchProgressSeconds: 0,
                isCompleted: false,
              ),
            ],
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            seriesDetailProvider(1).overrideWith((ref) => mockSeries),
          ],
          child: const MaterialApp(
            home: SeriesDetailScreen(seriesId: 1),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Destins Croisés'), findsOneWidget);
      expect(find.text('4.8'), findsOneWidget);
      expect(find.text('2024'), findsOneWidget);

      await tester.scrollUntilVisible(find.text('La Rencontre'), 200);
      expect(find.text('La Rencontre'), findsOneWidget);

      await tester.pumpWidget(const SizedBox());
    });
  });
}
