import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/localization/app_localizations.dart';
import '../core/services/video_player_manager.dart';
import '../core/theme/app_theme.dart';
import 'home/home_screen.dart';
import 'library/favorites_screen.dart';
import 'library/history_screen.dart';
import 'player/reels_screen.dart';
import 'settings/settings_screen.dart';
import '../core/services/update_service.dart';

/// Écran principal avec barre de navigation inférieure Netflix-style
class MainNavigationScreen extends ConsumerStatefulWidget {
  const MainNavigationScreen({super.key});

  @override
  ConsumerState<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends ConsumerState<MainNavigationScreen> {
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      UpdateService.checkForUpdates(context);
    });
  }

  void _onTabTapped(int index) {
    if (_currentIndex != index) {
      // Coupure immédiate du son de toute vidéo active lors d'un changement d'onglet
      ref.read(videoPlayerManagerProvider).pauseAll();
      setState(() {
        _currentIndex = index;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      body: IndexedStack(
        index: _currentIndex,
        children: [
          const HomeScreen(),
          ReelsScreen(isActive: _currentIndex == 1),
          const FavoritesScreen(),
          const HistoryScreen(),
          const SettingsScreen(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: _onTabTapped,
        backgroundColor: const Color(0xFF121212),
        selectedItemColor: Colors.white,
        unselectedItemColor: const Color(0xFF757575),
        selectedFontSize: 11,
        unselectedFontSize: 11,
        type: BottomNavigationBarType.fixed,
        items: [
          BottomNavigationBarItem(
            icon: const Icon(Icons.home_outlined),
            activeIcon: const Icon(Icons.home_filled),
            label: l10n.navHome,
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.movie_filter_outlined),
            activeIcon: const Icon(Icons.movie_filter),
            label: l10n.navReels,
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.bookmark_border),
            activeIcon: const Icon(Icons.bookmark),
            label: l10n.navMyList,
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.history_outlined),
            activeIcon: const Icon(Icons.history),
            label: l10n.navHistory,
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.settings_outlined),
            activeIcon: const Icon(Icons.settings),
            label: l10n.navSettings,
          ),
        ],
      ),
    );
  }
}
