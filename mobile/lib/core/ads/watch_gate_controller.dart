import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../models/user_model.dart';

/// Contrôleur de quota de visionnage et de déclenchement des publicités avec récompense AdMob.
///
/// Règles métier :
/// 1. Seuil aléatoire par cycle : entre 4 et 5 vidéos (configurable min/max).
/// 2. Critère de vidéo regardée : lue à au moins 70 % de sa durée totale, ou finie.
/// 3. Chaque vidéo n'est comptabilisée qu'une seule fois par cycle (Set<String>).
/// 4. Déblocage uniquement sur récompense confirmée (`onUserEarnedReward`).
/// 5. Persistance locale dans `SharedPreferences` résistante aux redémarrages.
/// 6. Exemption totale pour les comptes Administrateurs (`isAdmin`) et sans pub (`adsFree`).
class WatchGateController extends ChangeNotifier {
  // Clés SharedPreferences
  static const String keyWatchCount = 'ads_watch_gate_count';
  static const String keyCycleThreshold = 'ads_watch_gate_threshold';
  static const String keyGateLocked = 'ads_watch_gate_locked';
  static const String keyWatchedIds = 'ads_watch_gate_video_ids';

  // Paramètres configurables
  int minVideosPerCycle;
  int maxVideosPerCycle;
  double watchCompletionThreshold; // 0.70 = 70%

  // État interne
  int _watchedCount = 0;
  int _currentCycleThreshold = 4;
  bool _isGateLocked = false;
  final Set<String> _watchedVideoIds = {};
  bool _isInitialized = false;
  SharedPreferences? _prefs;

  // Singleton instance
  static final WatchGateController instance = WatchGateController._internal();

  WatchGateController._internal({
    this.minVideosPerCycle = 4,
    this.maxVideosPerCycle = 5,
    this.watchCompletionThreshold = 0.70,
  });

  /// Constructeur pour les tests ou instances personnalisées
  factory WatchGateController.custom({
    int minVideos = 4,
    int maxVideos = 5,
    double completionThreshold = 0.70,
    SharedPreferences? prefs,
  }) {
    final controller = WatchGateController._internal(
      minVideosPerCycle: minVideos,
      maxVideosPerCycle: maxVideos,
      watchCompletionThreshold: completionThreshold,
    );
    if (prefs != null) {
      controller._prefs = prefs;
    }
    return controller;
  }

  // Getters
  int get watchedCount => _watchedCount;
  int get currentCycleThreshold => _currentCycleThreshold;
  bool get isGateLocked => _isGateLocked;
  Set<String> get watchedVideoIds => Set.unmodifiable(_watchedVideoIds);
  bool get isInitialized => _isInitialized;

  /// Nombre de vidéos restantes avant le déclenchement de la prochaine publicité
  int get remainingVideos {
    final remaining = _currentCycleThreshold - _watchedCount;
    return remaining < 0 ? 0 : remaining;
  }

  /// Indique si le seuil du cycle courant est atteint
  bool get isThresholdReached => _watchedCount >= _currentCycleThreshold;

  /// Initialise l'état depuis le stockage persistant
  Future<void> initialize({SharedPreferences? prefs}) async {
    _prefs = prefs ?? await SharedPreferences.getInstance();

    _watchedCount = _prefs?.getInt(keyWatchCount) ?? 0;
    _isGateLocked = _prefs?.getBool(keyGateLocked) ?? false;
    final savedIds = _prefs?.getStringList(keyWatchedIds);
    if (savedIds != null) {
      _watchedVideoIds.clear();
      _watchedVideoIds.addAll(savedIds);
    }

    final savedThreshold = _prefs?.getInt(keyCycleThreshold);
    if (savedThreshold != null &&
        savedThreshold >= minVideosPerCycle &&
        savedThreshold <= maxVideosPerCycle) {
      _currentCycleThreshold = savedThreshold;
    } else {
      _currentCycleThreshold = _pickRandomThreshold();
      await _prefs?.setInt(keyCycleThreshold, _currentCycleThreshold);
    }

    // Cohérence de l'état bloqué
    if (_watchedCount >= _currentCycleThreshold) {
      _isGateLocked = true;
    }

    _isInitialized = true;
    notifyListeners();
  }

  /// Tire aléatoirement un seuil entre minVideosPerCycle et maxVideosPerCycle (ex: 4 ou 5)
  int _pickRandomThreshold() {
    if (maxVideosPerCycle <= minVideosPerCycle) {
      return minVideosPerCycle;
    }
    final rng = Random();
    return minVideosPerCycle + rng.nextInt(maxVideosPerCycle - minVideosPerCycle + 1);
  }

  /// Vérifie si l'utilisateur est exempté de publicités
  bool isUserExempt(UserModel? user) {
    if (user == null) return false;
    return user.isAdmin || user.adsFree;
  }

  /// Enregistre la progression de lecture d'une vidéo.
  ///
  /// Retourne `true` si le seuil est atteint et que la grille de pub est verrouillée.
  bool recordVideoProgress({
    required String videoId,
    required Duration position,
    required Duration duration,
    bool completed = false,
    UserModel? user,
  }) {
    // Si l'utilisateur est exempté (admin / sans pub), aucune pub
    if (isUserExempt(user)) {
      return false;
    }

    // Si déjà verrouillé, la pub doit être proposée
    if (_isGateLocked) {
      return true;
    }

    // Si la vidéo a déjà été comptabilisée dans ce cycle, ignorer
    if (_watchedVideoIds.contains(videoId)) {
      return false;
    }

    // Vérifier le critère d'éligibilité : finie ou >= 70% de la durée
    final bool isEligible = completed ||
        (duration.inMilliseconds > 0 &&
            (position.inMilliseconds / duration.inMilliseconds) >=
                watchCompletionThreshold);

    if (!isEligible) {
      return false;
    }

    // Comptabiliser la vidéo
    _watchedVideoIds.add(videoId);
    _watchedCount++;

    debugPrint(
      '[WatchGateController] Vidéo éligible comptée: $videoId '
      '($_watchedCount / $_currentCycleThreshold)',
    );

    // Vérifier si le quota du cycle est atteint
    if (_watchedCount >= _currentCycleThreshold) {
      _isGateLocked = true;
      debugPrint('[WatchGateController] Seuil atteint ! Accès vidéo verrouillé en attente d\'annonce.');
    }

    _saveState();
    notifyListeners();

    return _isGateLocked;
  }

  /// Débloque un nouveau cycle après confirmation de la récompense AdMob (`onUserEarnedReward`).
  ///
  /// Réinitialise le compteur, tire un nouveau seuil aléatoire (4 ou 5) et déverrouille l'accès.
  Future<void> unlockNewCycle() async {
    _watchedCount = 0;
    _watchedVideoIds.clear();
    _currentCycleThreshold = _pickRandomThreshold();
    _isGateLocked = false;

    debugPrint(
      '[WatchGateController] Récompense validée ! Nouveau cycle débloqué: '
      '0 / $_currentCycleThreshold vidéos.',
    );

    await _saveState();
    notifyListeners();
  }

  /// Verrouille manuellement la porte (par ex. si l'utilisateur a cliqué sur "Plus tard")
  Future<void> lockGate() async {
    _isGateLocked = true;
    await _saveState();
    notifyListeners();
  }

  /// Débloque temporairement l'accès en cas d'échec total du réseau/AdMob (fallback d'urgence)
  /// pour ne pas bloquer l'utilisateur de manière indue.
  Future<void> grantEmergencyBypass({int extraVideos = 1}) async {
    _isGateLocked = false;
    _currentCycleThreshold += extraVideos;
    debugPrint(
      '[WatchGateController] Dérogation d\'urgence accordée (+ $extraVideos vidéo(s)). '
      'Nouveau seuil temporaire: $_currentCycleThreshold',
    );
    await _saveState();
    notifyListeners();
  }

  /// Réinitialise complètement l'état (utile pour le panneau de diagnostic et les tests)
  Future<void> resetState({int? forcedThreshold}) async {
    _watchedCount = 0;
    _watchedVideoIds.clear();
    _currentCycleThreshold = forcedThreshold ?? _pickRandomThreshold();
    _isGateLocked = false;

    await _saveState();
    notifyListeners();
  }

  /// Sauvegarde l'état dans SharedPreferences
  Future<void> _saveState() async {
    final prefs = _prefs ?? await SharedPreferences.getInstance();
    await prefs.setInt(keyWatchCount, _watchedCount);
    await prefs.setInt(keyCycleThreshold, _currentCycleThreshold);
    await prefs.setBool(keyGateLocked, _isGateLocked);
    await prefs.setStringList(keyWatchedIds, _watchedVideoIds.toList());
  }
}

/// Provider Riverpod pour le contrôleur WatchGate
final watchGateProvider = ChangeNotifierProvider<WatchGateController>((ref) {
  return WatchGateController.instance;
});
