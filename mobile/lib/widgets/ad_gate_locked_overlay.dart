import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/localization/app_localizations.dart';
import '../core/theme/app_theme.dart';
import 'touchable_scale.dart';

/// Overlay de blocage du lecteur vidéo lorsque le quota de visionnage gratuit est atteint.
///
/// Affiche un écran sombre élégant empêchant la lecture vidéo et proposant le bouton
/// « Regarder la pub » pour débloquer le prochain lot d'épisodes.
class AdGateLockedOverlay extends StatelessWidget {
  final VoidCallback onWatchAd;
  final VoidCallback? onBack;

  const AdGateLockedOverlay({
    super.key,
    required this.onWatchAd,
    this.onBack,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;

    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          width: double.infinity,
          height: double.infinity,
          color: Colors.black.withValues(alpha: 0.85),
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              // Cadenas stylisé avec halo
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFF221118),
                  border: Border.all(color: AppTheme.netflixRed.withValues(alpha: 0.6), width: 2),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.netflixRed.withValues(alpha: 0.35),
                      blurRadius: 20,
                      spreadRadius: 2,
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.lock_rounded,
                  color: AppTheme.netflixRed,
                  size: 38,
                ),
              ),
              const SizedBox(height: 22),

              // Titre de verrouillage
              Text(
                l10n.adGateLockedTitle,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  letterSpacing: -0.3,
                ),
              ),
              const SizedBox(height: 10),

              // Message explicatif
              Text(
                l10n.adGateLockedMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 14,
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 28),

              // Bouton principal pour regarder la pub
              TouchableScale(
                onTap: () {
                  HapticFeedback.mediumImpact();
                  onWatchAd();
                },
                child: Container(
                  width: double.infinity,
                  constraints: const BoxConstraints(maxWidth: 320),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  decoration: BoxDecoration(
                    color: AppTheme.netflixRed,
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.netflixRed.withValues(alpha: 0.4),
                        blurRadius: 14,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.play_circle_filled, color: Colors.white, size: 22),
                      const SizedBox(width: 8),
                      Text(
                        l10n.adWatchButton,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              if (onBack != null) ...[
                const SizedBox(height: 12),
                TouchableScale(
                  onTap: () {
                    HapticFeedback.lightImpact();
                    onBack!();
                  },
                  child: Container(
                    width: double.infinity,
                    constraints: const BoxConstraints(maxWidth: 320),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.06),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.white12),
                    ),
                    child: Center(
                      child: Text(
                        l10n.cancel,
                        style: const TextStyle(
                          color: Colors.white60,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
