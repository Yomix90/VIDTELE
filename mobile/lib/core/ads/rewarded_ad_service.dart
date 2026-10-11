import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/legacy.dart';
import 'package:google_mobile_ads/google_mobile_ads.dart';

import 'ads_config.dart';
import 'consent_manager.dart';

/// États possibles du service d'annonces vidéo avec récompense
enum RewardedAdStatus {
  idle,
  loading,
  ready,
  showing,
  failed,
}

/// Service singleton gérant le cycle de vie complet des annonces Rewarded AdMob :
/// - Préchargement anticipé transparent
/// - Gestion des interruptions et callbacks plein écran
/// - Réessais avec backoff exponentiel (2s, 4s, 8s, 16s, 30s)
/// - Déblocage strict uniquement sur `onUserEarnedReward`
/// - Respect des règles RGPD / UMP via `ConsentManager`
class RewardedAdService extends ChangeNotifier {
  static final RewardedAdService instance = RewardedAdService._internal();
  RewardedAdService._internal();

  RewardedAd? _rewardedAd;
  RewardedAdStatus _status = RewardedAdStatus.idle;
  String? _lastError;
  int _retryAttempt = 0;
  Timer? _retryTimer;
  bool _isDisposed = false;

  RewardedAdStatus get status => _status;
  bool get isAdReady => _rewardedAd != null && _status == RewardedAdStatus.ready;
  String? get lastError => _lastError;

  /// Précharge une annonce vidéo avec récompense si aucune annonce n'est déjà prête ou en cours de chargement.
  Future<void> preloadAd() async {
    if (kIsWeb || _isDisposed) return;
    if (_rewardedAd != null || _status == RewardedAdStatus.loading || _status == RewardedAdStatus.showing) {
      return;
    }

    // Vérifier l'autorisation légale de demander des annonces (UMP / RGPD)
    final canRequest = await ConsentManager.instance.canRequestAds();
    if (!canRequest) {
      debugPrint('[RewardedAdService] Annonces non autorisées par le consentement UMP');
      _status = RewardedAdStatus.failed;
      _lastError = 'Consentement non accordé';
      notifyListeners();
      return;
    }

    _status = RewardedAdStatus.loading;
    _lastError = null;
    notifyListeners();

    final adUnitId = AdsConfig.rewardedAdUnitId;
    debugPrint('[RewardedAdService] Début du préchargement de l\'annonce (AdUnit: $adUnitId)...');

    try {
      await RewardedAd.load(
        adUnitId: adUnitId,
        request: const AdRequest(),
        rewardedAdLoadCallback: RewardedAdLoadCallback(
          onAdLoaded: (RewardedAd ad) {
            if (_isDisposed) {
              ad.dispose();
              return;
            }
            debugPrint('[RewardedAdService] Annonce avec récompense chargée avec succès !');
            _rewardedAd = ad;
            _status = RewardedAdStatus.ready;
            _retryAttempt = 0;
            _retryTimer?.cancel();
            _retryTimer = null;
            _lastError = null;
            _attachFullScreenCallbacks(ad);
            notifyListeners();
          },
          onAdFailedToLoad: (LoadAdError error) {
            debugPrint('[RewardedAdService] Échec du chargement de l\'annonce: ${error.message} (Code: ${error.code})');
            _rewardedAd = null;
            _status = RewardedAdStatus.failed;
            _lastError = error.message;
            notifyListeners();
            _scheduleRetry();
          },
        ),
      );
    } catch (e) {
      debugPrint('[RewardedAdService] Exception lors du chargement: $e');
      _status = RewardedAdStatus.failed;
      _lastError = e.toString();
      notifyListeners();
      _scheduleRetry();
    }
  }

  void _attachFullScreenCallbacks(RewardedAd ad) {
    ad.fullScreenContentCallback = FullScreenContentCallback(
      onAdShowedFullScreenContent: (RewardedAd ad) {
        debugPrint('[RewardedAdService] Annonce affichée en plein écran');
        _status = RewardedAdStatus.showing;
        notifyListeners();
      },
      onAdDismissedFullScreenContent: (RewardedAd ad) {
        debugPrint('[RewardedAdService] Annonce fermée par l\'utilisateur');
        ad.dispose();
        _rewardedAd = null;
        _status = RewardedAdStatus.idle;
        notifyListeners();

        // Préchargement immédiat de l'annonce suivante pour le prochain cycle
        preloadAd();
      },
      onAdFailedToShowFullScreenContent: (RewardedAd ad, AdError error) {
        debugPrint('[RewardedAdService] Échec affichage de l\'annonce: ${error.message}');
        ad.dispose();
        _rewardedAd = null;
        _status = RewardedAdStatus.failed;
        _lastError = error.message;
        notifyListeners();

        // Réessayer de précharger
        preloadAd();
      },
      onAdImpression: (RewardedAd ad) {
        debugPrint('[RewardedAdService] Impression d\'annonce enregistrée');
      },
      onAdClicked: (RewardedAd ad) {
        debugPrint('[RewardedAdService] Clic sur l\'annonce enregistré');
      },
    );
  }

  void _scheduleRetry() {
    if (_isDisposed) return;
    _retryAttempt++;
    if (_retryAttempt <= 4) {
      final delaySec = math.pow(2, _retryAttempt).toInt().clamp(2, 30);
      debugPrint('[RewardedAdService] Nouvelle tentative de préchargement dans ${delaySec}s (Essai $_retryAttempt/4)...');
      _retryTimer?.cancel();
      _retryTimer = Timer(Duration(seconds: delaySec), () {
        preloadAd();
      });
    } else {
      debugPrint('[RewardedAdService] Nombre maximum de tentatives atteint pour ce cycle.');
    }
  }

  /// Affiche l'annonce vidéo avec récompense et déclenche le callback de récompense uniquement si l'annonce est terminée.
  ///
  /// Retourne `true` si l'annonce a pu être lancée, `false` sinon.
  Future<bool> showRewardedAd({
    required void Function(RewardItem reward) onUserEarnedReward,
    VoidCallback? onAdClosed,
    void Function(String error)? onAdFailed,
  }) async {
    if (kIsWeb) {
      onUserEarnedReward(RewardItem(1, 'web_reward'));
      return true;
    }
    if (!isAdReady || _rewardedAd == null) {
      debugPrint('[RewardedAdService] Impossible d\'afficher: aucune annonce prête');
      onAdFailed?.call('Aucune annonce disponible pour le moment');
      preloadAd();
      return false;
    }

    final ad = _rewardedAd!;
    bool rewardEarned = false;

    // Mise à jour des callbacks pour cette session d'affichage
    ad.fullScreenContentCallback = FullScreenContentCallback(
      onAdShowedFullScreenContent: (RewardedAd ad) {
        _status = RewardedAdStatus.showing;
        notifyListeners();
      },
      onAdDismissedFullScreenContent: (RewardedAd ad) {
        ad.dispose();
        _rewardedAd = null;
        _status = RewardedAdStatus.idle;
        notifyListeners();
        if (!rewardEarned) {
          debugPrint('[RewardedAdService] Annonce fermée sans obtention de la récompense.');
        }
        onAdClosed?.call();
        // Précharger l'annonce suivante
        preloadAd();
      },
      onAdFailedToShowFullScreenContent: (RewardedAd ad, AdError error) {
        ad.dispose();
        _rewardedAd = null;
        _status = RewardedAdStatus.failed;
        _lastError = error.message;
        notifyListeners();
        onAdFailed?.call(error.message);
        preloadAd();
      },
    );

    try {
      await ad.show(
        onUserEarnedReward: (AdWithoutView ad, RewardItem reward) {
          debugPrint('[RewardedAdService] Récompense obtenue : ${reward.amount} ${reward.type}');
          rewardEarned = true;
          onUserEarnedReward(reward);
        },
      );
      return true;
    } catch (e) {
      debugPrint('[RewardedAdService] Erreur lors de l\'appel show(): $e');
      onAdFailed?.call(e.toString());
      return false;
    }
  }

  @override
  void dispose() {
    _isDisposed = true;
    _retryTimer?.cancel();
    _rewardedAd?.dispose();
    _rewardedAd = null;
    super.dispose();
  }
}

/// Provider Riverpod pour le service d'annonces récompensées
final rewardedAdServiceProvider = ChangeNotifierProvider<RewardedAdService>((ref) {
  final service = RewardedAdService.instance;
  // Déclencher le préchargement initial
  service.preloadAd();
  return service;
});
