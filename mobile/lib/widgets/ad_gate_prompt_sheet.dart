import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/localization/app_localizations.dart';
import '../core/theme/app_theme.dart';
import 'touchable_scale.dart';

/// Feuille modale (Bottom Sheet) de proposition d'annonce avec récompense.
///
/// Conforme aux directives AdMob & Google Play :
/// - Ne se lance JAMAIS automatiquement par surprise.
/// - Présente clairement la récompense (déblocage de vidéos).
/// - Propose un choix explicite avec deux boutons ("Regarder la pub" et "Plus tard").
class AdGatePromptSheet extends StatelessWidget {
  final int videosToUnlock;
  final VoidCallback onWatchAd;
  final VoidCallback onLater;

  const AdGatePromptSheet({
    super.key,
    required this.videosToUnlock,
    required this.onWatchAd,
    required this.onLater,
  });

  /// Méthode utilitaire statique pour afficher la feuille modale
  static Future<bool?> show(
    BuildContext context, {
    required int videosToUnlock,
    required VoidCallback onWatchAd,
    required VoidCallback onLater,
  }) {
    HapticFeedback.mediumImpact();
    return showModalBottomSheet<bool>(
      context: context,
      isDismissible: false,
      enableDrag: false,
      backgroundColor: Colors.transparent,
      builder: (ctx) => PopScope(
        canPop: false,
        child: AdGatePromptSheet(
          videosToUnlock: videosToUnlock,
          onWatchAd: () {
            Navigator.of(ctx).pop(true);
            onWatchAd();
          },
          onLater: () {
            Navigator.of(ctx).pop(false);
            onLater();
          },
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;

    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
      decoration: BoxDecoration(
        color: const Color(0xFF181824),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white12, width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.7),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Poignée supérieure discrète
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: Colors.white24,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 18),

          // Icône d'annonce avec récompense stylisée
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const LinearGradient(
                colors: [Color(0xFFE50914), Color(0xFFFF5252)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.netflixRed.withValues(alpha: 0.4),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: const Icon(
              Icons.stars_rounded,
              color: Colors.white,
              size: 34,
            ),
          ),
          const SizedBox(height: 18),

          // Titre
          Text(
            l10n.adRewardPromptTitle,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 19,
              fontWeight: FontWeight.bold,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 10),

          // Message explicatif
          Text(
            l10n.adRewardPromptMessage(videosToUnlock),
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 14,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 24),

          // Bouton primaire : "Regarder la pub"
          TouchableScale(
            onTap: onWatchAd,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 14),
              decoration: BoxDecoration(
                color: AppTheme.netflixRed,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.netflixRed.withValues(alpha: 0.3),
                    blurRadius: 10,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.play_arrow_rounded, color: Colors.white, size: 24),
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
          const SizedBox(height: 10),

          // Bouton secondaire : "Plus tard"
          TouchableScale(
            onTap: onLater,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.06),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white12),
              ),
              child: Center(
                child: Text(
                  l10n.adLaterButton,
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
      ),
    );
  }
}
