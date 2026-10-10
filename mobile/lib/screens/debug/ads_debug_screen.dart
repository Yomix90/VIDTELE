import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/ads/ads_config.dart';
import '../../core/ads/consent_manager.dart';
import '../../core/ads/rewarded_ad_service.dart';
import '../../core/ads/watch_gate_controller.dart';
import '../../core/theme/app_theme.dart';
import '../../widgets/touchable_scale.dart';

/// Écran de diagnostic et de test interactif pour AdMob & Annonces avec récompense.
class AdsDebugScreen extends ConsumerStatefulWidget {
  const AdsDebugScreen({super.key});

  @override
  ConsumerState<AdsDebugScreen> createState() => _AdsDebugScreenState();
}

class _AdsDebugScreenState extends ConsumerState<AdsDebugScreen> {
  int _rewardsEarnedCount = 0;
  String _lastEvent = 'Aucun événement pour le moment';

  @override
  Widget build(BuildContext context) {
    final adService = ref.watch(rewardedAdServiceProvider);
    final watchGate = ref.watch(watchGateProvider);

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      appBar: AppBar(
        title: const Text('Test & Diagnostic AdMob'),
        backgroundColor: AppTheme.darkSurface,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 1. Statut général
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF16161E),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white10),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: AdsConfig.isTestMode ? Colors.orange : Colors.green,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          AdsConfig.isTestMode ? 'MODE TEST GOOGLE' : 'MODE PRODUCTION',
                          style: const TextStyle(
                            color: Colors.black,
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      const Spacer(),
                      _buildStatusBadge(adService.status),
                    ],
                  ),
                  const SizedBox(height: 12),
                  const Text('App ID actif :', style: TextStyle(color: Colors.white54, fontSize: 12)),
                  Text(
                    AdsConfig.admobAppId,
                    style: const TextStyle(color: Colors.white, fontSize: 13, fontFamily: 'monospace'),
                  ),
                  const SizedBox(height: 8),
                  const Text('Bloc Rewarded actif :', style: TextStyle(color: Colors.white54, fontSize: 12)),
                  Text(
                    AdsConfig.rewardedAdUnitId,
                    style: const TextStyle(color: Colors.white, fontSize: 13, fontFamily: 'monospace'),
                  ),
                  if (adService.lastError != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      'Dernière erreur : ${adService.lastError}',
                      style: const TextStyle(color: Colors.redAccent, fontSize: 12),
                    ),
                  ],
                ],
              ),
            ),

            const SizedBox(height: 16),

            // 2. Statut WatchGate (Quota de visionnage)
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF16161E),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: watchGate.isGateLocked ? Colors.redAccent.withValues(alpha: 0.5) : Colors.greenAccent.withValues(alpha: 0.3),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        watchGate.isGateLocked ? Icons.lock : Icons.lock_open,
                        color: watchGate.isGateLocked ? Colors.redAccent : Colors.greenAccent,
                        size: 24,
                      ),
                      const SizedBox(width: 8),
                      const Text(
                        'Contrôleur de Quota (WatchGate)',
                        style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                      ),
                      const Spacer(),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: watchGate.isGateLocked
                              ? Colors.redAccent.withValues(alpha: 0.2)
                              : Colors.greenAccent.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          watchGate.isGateLocked ? 'BLOQUÉ (PUB REQUISE)' : 'ACCÈS LIBRE',
                          style: TextStyle(
                            color: watchGate.isGateLocked ? Colors.redAccent : Colors.greenAccent,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Progression du cycle :', style: TextStyle(color: Colors.white70, fontSize: 13)),
                      Text(
                        '${watchGate.watchedCount} / ${watchGate.currentCycleThreshold} vidéos',
                        style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: watchGate.currentCycleThreshold > 0
                          ? (watchGate.watchedCount / watchGate.currentCycleThreshold).clamp(0.0, 1.0)
                          : 0.0,
                      backgroundColor: Colors.white12,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        watchGate.isGateLocked ? Colors.redAccent : AppTheme.netflixRed,
                      ),
                      minHeight: 6,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    'Vidéos restantes avant pub : ${watchGate.remainingVideos}',
                    style: const TextStyle(color: Colors.white54, fontSize: 12),
                  ),
                  Text(
                    'Identifiants uniques comptés : ${watchGate.watchedVideoIds.length}',
                    style: const TextStyle(color: Colors.white38, fontSize: 11),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // 3. Compteur de récompenses
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF16161E),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.stars, color: Colors.amber, size: 36),
                  const SizedBox(width: 14),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Récompenses validées dans cette session',
                          style: TextStyle(color: Colors.white70, fontSize: 12)),
                      Text(
                        '$_rewardsEarnedCount annonce(s) terminée(s)',
                        style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // 4. Journal des derniers événements
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.black,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.white12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Dernier événement :', style: TextStyle(color: Colors.white38, fontSize: 11)),
                  const SizedBox(height: 4),
                  Text(_lastEvent, style: const TextStyle(color: Colors.greenAccent, fontSize: 12.5)),
                ],
              ),
            ),

            const SizedBox(height: 24),

            // 4. Actions interactives de test
            const Text(
              'Actions de test',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),

            // Bouton Précharger
            TouchableScale(
              onTap: () {
                HapticFeedback.lightImpact();
                setState(() => _lastEvent = 'Préchargement lancé...');
                adService.preloadAd();
              },
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 14),
                decoration: BoxDecoration(
                  color: const Color(0xFF222230),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white24),
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.download, color: Colors.white, size: 20),
                    SizedBox(width: 8),
                    Text('1. Précharger l\'annonce Rewarded',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 10),

            // Bouton Afficher
            TouchableScale(
              onTap: adService.isAdReady
                  ? () async {
                      HapticFeedback.mediumImpact();
                      setState(() => _lastEvent = 'Ouverture de l\'annonce plein écran...');
                      final ok = await adService.showRewardedAd(
                        onUserEarnedReward: (reward) {
                          setState(() {
                            _rewardsEarnedCount++;
                            _lastEvent = 'Récompense obtenue : ${reward.amount} ${reward.type} !';
                          });
                        },
                        onAdClosed: () {
                          setState(() {
                            _lastEvent += ' | Annonce fermée, préchargement suivant...';
                          });
                        },
                        onAdFailed: (err) {
                          setState(() => _lastEvent = 'Échec affichage : $err');
                        },
                      );
                      if (!ok) {
                        setState(() => _lastEvent = 'Impossible de lancer (annonce non prête)');
                      }
                    }
                  : null,
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 14),
                decoration: BoxDecoration(
                  color: adService.isAdReady ? AppTheme.netflixRed : Colors.white12,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.play_circle_filled,
                      color: adService.isAdReady ? Colors.white : Colors.white38,
                      size: 22,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '2. Afficher l\'annonce vidéo récompensée',
                      style: TextStyle(
                        color: adService.isAdReady ? Colors.white : Colors.white38,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),
            const Text(
              'Simulation Quota (WatchGate)',
              style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {
                      HapticFeedback.lightImpact();
                      final simId = 'sim_video_${DateTime.now().millisecondsSinceEpoch}';
                      final locked = watchGate.recordVideoProgress(
                        videoId: simId,
                        position: const Duration(seconds: 70),
                        duration: const Duration(seconds: 100),
                      );
                      setState(() {
                        _lastEvent = locked
                            ? 'Vidéo $simId lue (70%) -> SEUIL ATTEINT ET BLOQUÉ !'
                            : 'Vidéo $simId lue (70%) -> ${watchGate.watchedCount}/${watchGate.currentCycleThreshold}';
                      });
                    },
                    icon: const Icon(Icons.check_circle_outline, size: 16),
                    label: const Text('+1 Vue (70%)', style: TextStyle(fontSize: 12)),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      HapticFeedback.lightImpact();
                      await watchGate.unlockNewCycle();
                      setState(() {
                        _lastEvent = 'Cycle débloqué ! Nouveau seuil : ${watchGate.currentCycleThreshold}';
                      });
                    },
                    icon: const Icon(Icons.refresh, size: 16),
                    label: const Text('Débloquer', style: TextStyle(fontSize: 12)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      HapticFeedback.lightImpact();
                      await watchGate.lockGate();
                      setState(() => _lastEvent = 'Quota verrouillé manuellement');
                    },
                    icon: const Icon(Icons.lock, size: 16, color: Colors.redAccent),
                    label: const Text('Verrouiller', style: TextStyle(fontSize: 12, color: Colors.redAccent)),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      HapticFeedback.lightImpact();
                      await watchGate.resetState();
                      setState(() => _lastEvent = 'Compteur réinitialisé');
                    },
                    icon: const Icon(Icons.delete_outline, size: 16),
                    label: const Text('Reset', style: TextStyle(fontSize: 12)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // 5. Consentement UMP
            const Text(
              'Consentement RGPD / UMP',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),

            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () async {
                      HapticFeedback.lightImpact();
                      final can = await ConsentManager.instance.requestConsent();
                      setState(() {
                        _lastEvent = 'Consentement mis à jour : canRequestAds = $can';
                      });
                    },
                    child: const Text('Tester UMP'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton(
                    onPressed: () async {
                      HapticFeedback.lightImpact();
                      await ConsentManager.instance.reset();
                      setState(() => _lastEvent = 'Consentement réinitialisé');
                    },
                    child: const Text('Reset UMP'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBadge(RewardedAdStatus status) {
    Color color;
    String text;

    switch (status) {
      case RewardedAdStatus.idle:
        color = Colors.white38;
        text = 'IDLE';
        break;
      case RewardedAdStatus.loading:
        color = Colors.blueAccent;
        text = 'CHARGEMENT...';
        break;
      case RewardedAdStatus.ready:
        color = Colors.greenAccent;
        text = 'PRÊTE À DIFFUSER';
        break;
      case RewardedAdStatus.showing:
        color = Colors.purpleAccent;
        text = 'EN COURS DE LECTURE';
        break;
      case RewardedAdStatus.failed:
        color = Colors.redAccent;
        text = 'ÉCHEC CHARGEMENT';
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        border: Border.all(color: color.withValues(alpha: 0.5)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold),
      ),
    );
  }
}
