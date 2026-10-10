import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';
import 'package:vidtele_mobile/core/services/video_player_manager.dart';

/// Test double pour vérifier les interactions de navigation
class MockPlayerController extends VideoPlayerController {
  bool isPlayingState = false;

  MockPlayerController() : super.networkUrl(Uri.parse('https://example.com/test.mp4')) {
    value = const VideoPlayerValue(
      duration: Duration(seconds: 120),
      isInitialized: true,
      isPlaying: false,
    );
  }

  @override
  Future<void> play() async {
    isPlayingState = true;
    value = value.copyWith(isPlaying: true);
  }

  @override
  Future<void> pause() async {
    isPlayingState = false;
    value = value.copyWith(isPlaying: false);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Changer d\'onglet coupe immédiatement le lecteur vidéo actif', (WidgetTester tester) async {
    final manager = VideoPlayerManager();
    final controller = MockPlayerController();

    manager.registerPlayer(id: 'tab_reel_1', controller: controller);
    await manager.play('tab_reel_1');
    expect(controller.isPlayingState, isTrue);

    int currentIndex = 1; // Onglet Reels actif

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          videoPlayerManagerProvider.overrideWithValue(manager),
        ],
        child: MaterialApp(
          home: StatefulBuilder(
            builder: (context, setState) {
              return Scaffold(
                body: Text('Page $currentIndex'),
                bottomNavigationBar: BottomNavigationBar(
                  currentIndex: currentIndex,
                  onTap: (newIndex) {
                    if (currentIndex != newIndex) {
                      manager.pauseAll();
                      setState(() {
                        currentIndex = newIndex;
                      });
                    }
                  },
                  items: const [
                    BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Accueil'),
                    BottomNavigationBarItem(icon: Icon(Icons.movie), label: 'Reels'),
                    BottomNavigationBarItem(icon: Icon(Icons.bookmark), label: 'Ma liste'),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );

    expect(controller.isPlayingState, isTrue);

    // Clic sur l'onglet 0 (Accueil)
    await tester.tap(find.text('Accueil'));
    await tester.pumpAndSettle();

    // Vérification de la coupure immédiate
    expect(currentIndex, 0);
    expect(controller.isPlayingState, isFalse);
    expect(manager.activePlayerId, isNull);
  });
}
