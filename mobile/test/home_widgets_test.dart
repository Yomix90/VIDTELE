import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vidtele_mobile/models/home_model.dart';
import 'package:vidtele_mobile/widgets/hero_slider.dart';
import 'package:vidtele_mobile/widgets/top_number_card.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('HomeScreen Models & Widgets Tests', () {
    test('HomeScreenData fromJson parses complete API payload', () {
      final json = {
        'hero': [
          {
            'id': 10,
            'title': 'Revenge of the CEO',
            'title_fr': 'La Revanche du PDG',
            'synopsis': 'Un jeune homme trahi prend sa revanche...',
            'poster_path': '/posters/ceo.jpg',
            'banner_path': '/banners/ceo.jpg',
            'year': 2026,
            'rating': 4.9,
            'category': 'Micro-série',
            'episodes_count': 60,
            'first_video_id': 101,
          }
        ],
        'top5': [
          {
            'id': 10,
            'rank': 1,
            'title': 'La Revanche du PDG',
            'rating': 4.9,
            'poster_path': '/posters/ceo.jpg',
            'episodes_count': 60,
            'views_last_7d': 1420,
          },
          {
            'id': 12,
            'rank': 2,
            'title': 'Amour & Complots',
            'rating': 4.7,
            'poster_path': '/posters/amour.jpg',
            'episodes_count': 45,
            'views_last_7d': 980,
          },
        ],
        'continue_watching': [],
        'new_releases': [],
        'trending': [],
        'genres': [
          {
            'name': 'Drame',
            'count': 12,
            'items': [],
          }
        ],
      };

      final data = HomeScreenData.fromJson(json);

      expect(data.hero.length, 1);
      expect(data.hero.first.titleFr, 'La Revanche du PDG');
      expect(data.hero.first.episodesCount, 60);

      expect(data.top5.length, 2);
      expect(data.top5.first.rank, 1);
      expect(data.top5.first.viewsLast7d, 1420);

      expect(data.genres.length, 1);
      expect(data.genres.first.name, 'Drame');
    });

    testWidgets('TopNumberCard renders giant rank and series title', (tester) async {
      bool tapped = false;
      final series = TopSeriesModel(
        id: 10,
        rank: 1,
        title: 'La Revanche du PDG',
        rating: 4.8,
        posterPath: null,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TopNumberCard.fromSeries(
              rank: 1,
              series: series,
              onTap: () {
                tapped = true;
              },
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('1'), findsWidgets);
      expect(find.text('La Revanche du PDG'), findsOneWidget);
      expect(find.text('4.8'), findsOneWidget);

      await tester.tap(find.text('La Revanche du PDG'));
      await tester.pumpAndSettle();
      expect(tapped, isTrue);
    });

    testWidgets('HeroSlider renders items and watch button', (tester) async {
      HomeHeroItem? watchedItem;
      final items = [
        HomeHeroItem(
          id: 1,
          title: 'Série Test 1',
          titleFr: 'Série Test 1',
          synopsis: 'Synopsis court pour test',
          category: 'Micro-série',
          episodesCount: 30,
        ),
        HomeHeroItem(
          id: 2,
          title: 'Série Test 2',
          titleFr: 'Série Test 2',
          synopsis: 'Deuxième série de test',
          category: 'Action',
          episodesCount: 50,
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: HeroSlider(
                items: items,
                onWatch: (item) {
                  watchedItem = item;
                },
              ),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Série Test 1'), findsOneWidget);
      expect(find.text('MICRO-SÉRIE'), findsOneWidget);
      expect(find.text('30 épisodes'), findsOneWidget);

      // Le bouton regarder est présent
      expect(find.byIcon(Icons.play_arrow), findsOneWidget);

      await tester.tap(find.byIcon(Icons.play_arrow));
      await tester.pumpAndSettle();

      expect(watchedItem, isNotNull);
      expect(watchedItem!.id, 1);
    });
  });
}
