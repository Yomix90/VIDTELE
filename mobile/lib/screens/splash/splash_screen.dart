import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ads/consent_manager.dart';
import '../../core/ads/rewarded_ad_service.dart';
import '../../core/ads/watch_gate_controller.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../auth/login_screen.dart';
import '../main_navigation_screen.dart';

/// Écran d'accueil cinématique au démarrage (Splash Screen) avec logo animé et indicateur de chargement.
class SplashScreen extends ConsumerStatefulWidget {
  final Duration minDuration;

  const SplashScreen({
    super.key,
    this.minDuration = const Duration(milliseconds: 1200),
  });

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _animController;
  late final Animation<double> _scaleAnimation;
  late final Animation<double> _opacityAnimation;
  Timer? _delayTimer;

  @override
  void initState() {
    super.initState();

    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);

    _scaleAnimation = Tween<double>(begin: 0.94, end: 1.04).animate(
      CurvedAnimation(parent: _animController, curve: Curves.easeInOut),
    );

    _opacityAnimation = Tween<double>(begin: 0.85, end: 1.0).animate(
      CurvedAnimation(parent: _animController, curve: Curves.easeInOut),
    );

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _initializeApp();
    });
  }

  Future<void> _initializeApp() async {
    final startTime = DateTime.now();

    // 1. Initialisations asynchrones sans bloquer l'affichage de l'écran
    try {
      await ref.read(authProvider.notifier).checkInitialAuth();
    } catch (_) {}

    try {
      WatchGateController.instance.initialize().catchError((_) {});
      ConsentManager.instance.requestConsent().catchError((_) => true);
      RewardedAdService.instance.preloadAd();
    } catch (_) {}

    // 2. Assurer la durée minimale d'affichage si demandée
    if (widget.minDuration > Duration.zero) {
      final elapsed = DateTime.now().difference(startTime);
      if (elapsed < widget.minDuration) {
        final completer = Completer<void>();
        _delayTimer = Timer(widget.minDuration - elapsed, () {
          if (!completer.isCompleted) completer.complete();
        });
        await completer.future;
      }
    }

    if (!mounted) return;

    // 3. Navigation vers l'écran principal ou la connexion
    final isAuthenticated = ref.read(authProvider).isAuthenticated;
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        transitionDuration: const Duration(milliseconds: 600),
        pageBuilder: (_, __, ___) =>
            isAuthenticated ? const MainNavigationScreen() : const LoginScreen(),
        transitionsBuilder: (_, animation, __, child) {
          return FadeTransition(opacity: animation, child: child);
        },
      ),
    );
  }

  @override
  void dispose() {
    _delayTimer?.cancel();
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // 1. Dégradé de fond subtil avec lueur rouge centrale
          Positioned.fill(
            child: Container(
              decoration: const BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment.center,
                  radius: 0.9,
                  colors: [
                    Color(0xFF200B12), // Teinte bordeaux sombre
                    AppTheme.netflixBlack,
                  ],
                ),
              ),
            ),
          ),

          // 2. Contenu central : Icône de l'application + Titre + Loading
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Icône avec animation de pulsation douce
                AnimatedBuilder(
                  animation: _animController,
                  builder: (context, child) {
                    return Transform.scale(
                      scale: _scaleAnimation.value,
                      child: Opacity(
                        opacity: _opacityAnimation.value,
                        child: child,
                      ),
                    );
                  },
                  child: Container(
                    width: 105,
                    height: 105,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(22),
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.netflixRed.withValues(alpha: 0.45),
                          blurRadius: 28,
                          spreadRadius: 2,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(22),
                      child: Image.asset(
                        'assets/images/atlas_play_icon.png',
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Container(
                          color: AppTheme.netflixRed,
                          child: const Icon(Icons.play_arrow_rounded, color: Colors.white, size: 64),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 26),

                // Titre cinématique
                const Text(
                  'ATLAS PLAY',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 26,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 4.5,
                    shadows: [
                      Shadow(
                        color: Color(0x99E50914),
                        blurRadius: 18,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 38),

                // Animation de chargement élégante
                const SizedBox(
                  width: 32,
                  height: 32,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.8,
                    valueColor: AlwaysStoppedAnimation<Color>(AppTheme.netflixRed),
                  ),
                ),
              ],
            ),
          ),

          // 3. Mention de bas de page cinématique
          const Positioned(
            bottom: 28,
            left: 0,
            right: 0,
            child: Text(
              'VIDÉOS & SÉRIES COURTES',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white38,
                fontSize: 11,
                letterSpacing: 2.5,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
