import 'dart:async';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';

import '../../core/ads/rewarded_ad_service.dart';
import '../../core/ads/watch_gate_controller.dart';
import '../../core/api/api_client.dart';
import '../../core/constants/api_constants.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/services/video_player_manager.dart';
import '../../core/services/video_watchdog.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../core/utils/image_utils.dart';
import '../../models/feed_model.dart';
import '../../models/video_model.dart';
import '../../providers/auth_provider.dart';
import '../../providers/feed_provider.dart';
import '../../providers/library_provider.dart';
import '../../providers/video_provider.dart';
import '../../widgets/ad_gate_locked_overlay.dart';
import '../../widgets/ad_gate_prompt_sheet.dart';
import '../../widgets/empty_state.dart';
import '../../widgets/error_state.dart';
import '../../widgets/touchable_scale.dart';

/// Lecteur vertical unique plein écran pour toutes les vidéos et séries de l'application (style TikTok / ReelShort / Netflix).
/// Caractéristiques techniques majeures :
/// - Composant unifié pour toutes les entrées (Accueil, Top 5, Slider, Recherche, Ma Liste, Historique, Détail)
/// - Pool strict de MAX 3 contrôleurs vidéo (focused - 1, focused, focused + 1)
/// - Détection proactive des blocages (Watchdog 8s) et reconnexion automatique en cas de coupure (jusqu'à 3x)
/// - Enchaînement immédiat d'épisodes avec préchargement anticipé 5-10s avant la fin (zéro latence)
/// - Carte cinématique « Série terminée » avec séries recommandées (lancement direct)
/// - Support complet des playlists personnalisées et des films/vidéos autonomes
/// - Intégration stricte de la monétisation AdMob Rewarded avec consentement explicite (AdGate)
class ReelsScreen extends ConsumerStatefulWidget {
  final bool isActive;
  final int? seriesId;
  final int? initialVideoId;
  final VideoModel? initialVideo;
  final List<VideoModel>? playlist;
  final bool isStandalone;

  const ReelsScreen({
    super.key,
    this.isActive = true,
    this.seriesId,
    this.initialVideoId,
    this.initialVideo,
    this.playlist,
    this.isStandalone = false,
  });

  @override
  ConsumerState<ReelsScreen> createState() => _ReelsScreenState();
}

class _ReelsScreenState extends ConsumerState<ReelsScreen>
    with WidgetsBindingObserver
    implements VideoWatchdogDelegate {
  late final PageController _pageController;
  int _focusedIndex = 0;
  bool _isAppActive = true;
  double _playbackSpeed = 1.0;
  bool _isMuted = false;

  // Pool de contrôleurs limité à MAX 3 en mémoire
  final Map<int, VideoPlayerController> _controllerPool = {};
  final Set<int> _initializingIndices = {};

  // Watchdog de résilience
  VideoWatchdog? _watchdog;

  // Playlist personnalisée passée en paramètre
  List<FeedItemModel>? _customPlaylistItems;
  bool _hasJumpedToInitial = false;

  Timer? _progressSyncTimer;

  // Animation cœur double-tap
  bool _showHeartAnimation = false;
  Offset _heartPosition = Offset.zero;

  // Contrôle de quota AdGate
  bool _showingAdGatePrompt = false;
  bool _isGateLockedLocally = false;

  VideoPlayerManager? _videoPlayerManager;

  @override
  void initState() {
    super.initState();
    _videoPlayerManager = ref.read(videoPlayerManagerProvider);
    WidgetsBinding.instance.addObserver(this);

    // Initialisation depuis une playlist personnalisée si fournie
    if (widget.playlist != null && widget.playlist!.isNotEmpty) {
      _customPlaylistItems = widget.playlist!.map(_videoToFeedItem).toList();
      int initialIdx = 0;
      if (widget.initialVideoId != null) {
        initialIdx = _customPlaylistItems!.indexWhere((it) => it.id == widget.initialVideoId);
      } else if (widget.initialVideo != null) {
        initialIdx = _customPlaylistItems!.indexWhere((it) => it.id == widget.initialVideo!.id);
      }
      if (initialIdx < 0) initialIdx = 0;
      _focusedIndex = initialIdx;
      _hasJumpedToInitial = true;
      _pageController = PageController(initialPage: initialIdx);
    } else if (widget.initialVideo != null) {
      _customPlaylistItems = [_videoToFeedItem(widget.initialVideo!)];
      _focusedIndex = 0;
      _hasJumpedToInitial = true;
      _pageController = PageController(initialPage: 0);
    } else {
      _pageController = PageController();
    }

    _startProgressSyncTimer();
  }

  @override
  void didUpdateWidget(covariant ReelsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.isActive && oldWidget.isActive) {
      // Coupure immédiate du son et du timer quand le composant n'est plus actif
      _progressSyncTimer?.cancel();
      _progressSyncTimer = null;
      _videoPlayerManager?.pauseAll();
      _watchdog?.setPlaybackDesired(false);
    } else if (widget.isActive && !oldWidget.isActive) {
      // Reprise de la vidéo visible et du timer
      _startProgressSyncTimer();
      final feedState = _getFeedState();
      _reconcileControllers(_focusedIndex, feedState.items);
      _watchdog?.setPlaybackDesired(true);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _isAppActive = false;
      _progressSyncTimer?.cancel();
      _progressSyncTimer = null;
      _videoPlayerManager?.pauseAll();
      _watchdog?.setPlaybackDesired(false);
    } else if (state == AppLifecycleState.inactive) {
      // Sous Android, inactive est émis lors d'une notification ou du volet de statut.
      // Ne pas couper la lecture en premier plan !
      debugPrint('[ReelsScreen] AppLifecycleState.inactive ignoré pour maintenir le streaming');
    } else if (state == AppLifecycleState.resumed) {
      _isAppActive = true;
      if (widget.isActive) {
        _startProgressSyncTimer();
        final feedState = _getFeedState();
        _reconcileControllers(_focusedIndex, feedState.items);
        _watchdog?.setPlaybackDesired(true);
      }
    }
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _progressSyncTimer?.cancel();
    _progressSyncTimer = null;

    _watchdog?.dispose();
    _watchdog = null;

    // Libération stricte et exhaustive de tous les contrôleurs du pool
    for (final entry in _controllerPool.entries) {
      final ctrl = entry.value;
      ctrl.pause();
      ctrl.dispose();
    }
    _controllerPool.clear();
    _initializingIndices.clear();

    _videoPlayerManager?.pauseAll();
    _pageController.dispose();
    super.dispose();
  }

  FeedState _getFeedState() {
    if (_customPlaylistItems != null) {
      return FeedState(
        items: _customPlaylistItems!,
        isLoading: false,
        hasMore: false,
      );
    }
    return widget.seriesId != null
        ? ref.read(seriesFeedNotifierProvider(widget.seriesId!))
        : ref.read(feedNotifierProvider);
  }

  static FeedItemModel _videoToFeedItem(VideoModel v) {
    return FeedItemModel(
      id: v.id,
      telegramMessageId: v.telegramMessageId,
      title: v.title,
      seasonNumber: v.seasonNumber ?? 1,
      episodeNumber: v.episodeNumber ?? 1,
      episodeTitle: v.episodeTitle,
      caption: v.caption,
      category: v.category,
      durationSeconds: v.durationSeconds,
      fileSizeBytes: v.fileSizeBytes,
      mimeType: v.mimeType,
      thumbnailPath: v.thumbnailPath,
      viewsCount: v.viewsCount,
      isFavorite: v.isFavorite,
      watchProgressSeconds: v.watchProgressSeconds,
      isCompleted: v.isCompleted,
      streamUrl: ApiConstants.videoStream(v.id),
      seriesId: v.seriesId,
    );
  }

  // =========================================================================
  // Implémentation du VideoWatchdogDelegate (Résilience & Reconnexion Auto)
  // =========================================================================

  @override
  Future<bool> onReloadRequested({
    required Duration resumePosition,
    required int attempt,
  }) async {
    final feedState = _getFeedState();
    if (_focusedIndex >= feedState.items.length) return false;
    final item = feedState.items[_focusedIndex];

    try {
      debugPrint('[ReelsScreen] Watchdog: tentative $attempt de réinitialisation du flux pour ${item.id} à ${resumePosition.inSeconds}s');
      final baseUrl = await storageService.getServerUrl();
      final accessToken = await storageService.getAccessToken();

      String? streamToken;
      try {
        final tokenRes = await apiClient.dio.get(
          ApiConstants.videoStreamToken(item.id),
        );
        streamToken = tokenRes.data['stream_token'];
      } catch (_) {
        streamToken = accessToken;
      }

      final streamUri = Uri.parse(
        '$baseUrl${ApiConstants.videoStream(item.id)}?token=$streamToken',
      );

      final oldCtrl = _controllerPool[_focusedIndex];
      oldCtrl?.pause();
      oldCtrl?.dispose();

      final newCtrl = VideoPlayerController.networkUrl(
        streamUri,
        httpHeaders: {
          if (accessToken != null) 'Authorization': 'Bearer $accessToken',
        },
      );

      await newCtrl.initialize();
      newCtrl.setPlaybackSpeed(_playbackSpeed);
      newCtrl.setVolume(_isMuted ? 0.0 : 1.0);

      if (resumePosition > Duration.zero && resumePosition < newCtrl.value.duration) {
        await newCtrl.seekTo(resumePosition);
      }

      final playerId = 'feed_${item.id}';
      ref.read(videoPlayerManagerProvider).registerPlayer(
        id: playerId,
        controller: newCtrl,
        onPauseRequested: () {
          if (mounted) setState(() {});
        },
      );

      // Ré-attacher l'écouteur de fin de vidéo pour le mode binge
      newCtrl.addListener(() {
        if (!mounted || _focusedIndex >= feedState.items.length) return;
        final pos = newCtrl.value.position;
        final dur = newCtrl.value.duration;

        // Préchargement anticipé 8s avant la fin
        if (dur > Duration.zero && pos >= dur - const Duration(seconds: 8)) {
          _preloadNextController(feedState.items);
        }

        if (dur > Duration.zero && pos >= dur - const Duration(milliseconds: 500) && !newCtrl.value.isPlaying) {
          _onVideoEnded();
        }
      });

      _controllerPool[_focusedIndex] = newCtrl;
      _watchdog?.attach(newCtrl, isPlaybackDesired: widget.isActive && _isAppActive);

      if (mounted) setState(() {});
      if (widget.isActive && _isAppActive) {
        await ref.read(videoPlayerManagerProvider).play(playerId);
      }
      return true;
    } catch (e) {
      debugPrint('[ReelsScreen] Watchdog: échec du rechargement de source: $e');
      return false;
    }
  }

  @override
  void onFatalError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.wifi_off_rounded, color: Colors.white, size: 20),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: AppTheme.netflixRed,
        duration: const Duration(seconds: 5),
        action: SnackBarAction(
          label: 'Réessayer',
          textColor: Colors.white,
          onPressed: () {
            final feedState = _getFeedState();
            _reconcileControllers(_focusedIndex, feedState.items);
          },
        ),
      ),
    );
  }

  @override
  void onHealthStatusChanged(VideoHealthStatus status) {
    if (mounted) setState(() {});
  }

  void _attachWatchdog(int index, List<FeedItemModel> items) {
    if (index >= items.length) return;
    final item = items[index];
    final ctrl = _controllerPool[index];
    if (ctrl == null) return;

    _watchdog?.dispose();
    _watchdog = VideoWatchdog(
      videoId: item.id.toString(),
      delegate: this,
      stallThreshold: const Duration(seconds: 8),
      maxRetries: 3,
    );
    _watchdog!.attach(ctrl, isPlaybackDesired: widget.isActive && _isAppActive);
  }

  // =========================================================================
  // Gating publicitaire AdMob Rewarded
  // =========================================================================

  void _checkAdGate(String videoId, Duration position, Duration duration, {bool completed = false}) {
    if (_showingAdGatePrompt || !mounted) return;
    final user = ref.read(authProvider).user;
    final watchGate = ref.read(watchGateProvider);

    if (watchGate.isGateLocked && !watchGate.isUserExempt(user)) {
      _triggerAdGate();
      return;
    }

    final isLocked = watchGate.recordVideoProgress(
      videoId: videoId,
      position: position,
      duration: duration,
      completed: completed,
      user: user,
    );

    if (isLocked) {
      _triggerAdGate();
    }
  }

  void _triggerAdGate() {
    if (_showingAdGatePrompt || !mounted) return;
    _showingAdGatePrompt = true;

    final ctrl = _controllerPool[_focusedIndex];
    ctrl?.pause();
    _videoPlayerManager?.pauseAll();
    _watchdog?.setPlaybackDesired(false);

    setState(() {
      _isGateLockedLocally = true;
    });

    final watchGate = ref.read(watchGateProvider);
    final count = watchGate.currentCycleThreshold;

    AdGatePromptSheet.show(
      context,
      videosToUnlock: count,
      onWatchAd: _launchRewardedAd,
      onLater: () {
        if (!mounted) return;
        setState(() {
          _showingAdGatePrompt = false;
          _isGateLockedLocally = true;
        });
      },
    ).then((_) {
      if (mounted) {
        setState(() => _showingAdGatePrompt = false);
      }
    });
  }

  Future<void> _launchRewardedAd() async {
    final adService = ref.read(rewardedAdServiceProvider);
    final watchGate = ref.read(watchGateProvider);
    final l10n = context.l10n;

    bool rewardEarned = false;

    final success = await adService.showRewardedAd(
      onUserEarnedReward: (reward) {
        rewardEarned = true;
      },
      onAdClosed: () async {
        if (rewardEarned) {
          await watchGate.unlockNewCycle();
          if (mounted) {
            setState(() {
              _isGateLockedLocally = false;
              _showingAdGatePrompt = false;
            });
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Row(
                  children: [
                    const Icon(Icons.check_circle, color: Colors.greenAccent),
                    const SizedBox(width: 8),
                    Text('${watchGate.currentCycleThreshold} nouvelles vidéos débloquées !'),
                  ],
                ),
                backgroundColor: AppTheme.darkSurface,
                duration: const Duration(seconds: 3),
              ),
            );
            final feedState = _getFeedState();
            if (_focusedIndex < feedState.items.length) {
              final vidId = feedState.items[_focusedIndex].id;
              _videoPlayerManager?.play('feed_$vidId');
              _watchdog?.setPlaybackDesired(true);
            }
          }
        } else {
          if (mounted) {
            setState(() {
              _isGateLockedLocally = true;
              _showingAdGatePrompt = false;
            });
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(l10n.adNotCompletedWarning),
                backgroundColor: AppTheme.netflixRed,
                duration: const Duration(seconds: 3),
              ),
            );
          }
        }
      },
      onAdFailed: (error) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(l10n.adUnavailableMessage),
              backgroundColor: AppTheme.darkSurface,
              action: SnackBarAction(
                label: 'Continuer',
                onPressed: () {
                  watchGate.grantEmergencyBypass();
                  setState(() => _isGateLockedLocally = false);
                  final feedState = _getFeedState();
                  if (_focusedIndex < feedState.items.length) {
                    final vidId = feedState.items[_focusedIndex].id;
                    _videoPlayerManager?.play('feed_$vidId');
                    _watchdog?.setPlaybackDesired(true);
                  }
                },
              ),
            ),
          );
        }
      },
    );

    if (!success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(l10n.adUnavailableMessage),
          backgroundColor: AppTheme.darkSurface,
          action: SnackBarAction(
            label: 'Continuer',
            onPressed: () {
              watchGate.grantEmergencyBypass();
              setState(() => _isGateLockedLocally = false);
              final feedState = _getFeedState();
              if (_focusedIndex < feedState.items.length) {
                final vidId = feedState.items[_focusedIndex].id;
                _videoPlayerManager?.play('feed_$vidId');
                _watchdog?.setPlaybackDesired(true);
              }
            },
          ),
        ),
      );
    }
  }

  // =========================================================================
  // Progression & Synchronisation
  // =========================================================================

  void _startProgressSyncTimer() {
    _progressSyncTimer?.cancel();
    if (!widget.isActive || !_isAppActive) return;
    _progressSyncTimer = Timer.periodic(const Duration(seconds: 4), (_) {
      final ctrl = _controllerPool[_focusedIndex];
      if (ctrl != null && ctrl.value.isInitialized && ctrl.value.isPlaying) {
        final feedState = _getFeedState();
        if (_focusedIndex < feedState.items.length) {
          final item = feedState.items[_focusedIndex];
          final pos = ctrl.value.position.inSeconds.toDouble();
          final durationSec = ctrl.value.duration.inSeconds;
          final completed = (durationSec > 0) && (pos >= durationSec - 3);

          _checkAdGate(item.id.toString(), ctrl.value.position, ctrl.value.duration, completed: completed);

          try {
            apiClient.dio.put(
              ApiConstants.videoProgress(item.id),
              data: {
                'position_seconds': pos,
                'completed': completed,
              },
            );
          } catch (_) {}
        }
      }
    });
  }

  // =========================================================================
  // Gestion du Pool de Contrôleurs & Préchargement Anticipé
  // =========================================================================

  void _reconcileControllers(int currentIndex, List<FeedItemModel> items) {
    if (items.isEmpty) return;

    // 1. Les 3 indices cibles autorisés dans le pool
    final targetIndices = <int>{};
    if (currentIndex - 1 >= 0) targetIndices.add(currentIndex - 1);
    targetIndices.add(currentIndex);
    if (currentIndex + 1 < items.length) targetIndices.add(currentIndex + 1);

    // 2. Éjecter et libérer IMMÉDIATEMENT tout contrôleur hors cible
    final toRemove = _controllerPool.keys.where((k) => !targetIndices.contains(k)).toList();
    for (final oldIdx in toRemove) {
      final ctrl = _controllerPool.remove(oldIdx);
      if (oldIdx < items.length) {
        final vidId = items[oldIdx].id;
        ref.read(videoPlayerManagerProvider).unregisterPlayer('feed_$vidId');
      }
      ctrl?.pause();
      ctrl?.dispose();
    }

    // 3. Initialiser les contrôleurs cibles manquants
    for (final idx in targetIndices) {
      if (!_controllerPool.containsKey(idx) && !_initializingIndices.contains(idx)) {
        _initControllerForIndex(idx, items[idx]);
      }
    }

    // 4. Mettre à jour la lecture : seul l'index visible joue
    for (final idx in _controllerPool.keys) {
      if (idx < items.length) {
        final vidId = items[idx].id;
        final playerId = 'feed_$vidId';

        if (idx == currentIndex && widget.isActive && _isAppActive) {
          ref.read(videoPlayerManagerProvider).play(playerId);
          _attachWatchdog(currentIndex, items);
        } else {
          ref.read(videoPlayerManagerProvider).pause(playerId);
        }
      }
    }
  }

  void _preloadNextController(List<FeedItemModel> items) {
    final nextIdx = _focusedIndex + 1;
    if (nextIdx < items.length && !_controllerPool.containsKey(nextIdx) && !_initializingIndices.contains(nextIdx)) {
      debugPrint('[ReelsScreen] Préchargement anticipé de l\'épisode suivant (index $nextIdx)');
      _initControllerForIndex(nextIdx, items[nextIdx]);
    }
  }

  Future<void> _initControllerForIndex(int idx, FeedItemModel item) async {
    _initializingIndices.add(idx);

    try {
      final baseUrl = await storageService.getServerUrl();
      final accessToken = await storageService.getAccessToken();

      // Utilisation du verbe GET standardisé pour stream-token
      String? streamToken;
      try {
        final tokenRes = await apiClient.dio.get(
          ApiConstants.videoStreamToken(item.id),
        );
        streamToken = tokenRes.data['stream_token'];
      } catch (_) {
        streamToken = accessToken;
      }

      final streamUri = Uri.parse(
        '$baseUrl${ApiConstants.videoStream(item.id)}?token=$streamToken',
      );

      final ctrl = VideoPlayerController.networkUrl(
        streamUri,
        httpHeaders: {
          if (accessToken != null) 'Authorization': 'Bearer $accessToken',
        },
      );

      await ctrl.initialize();
      ctrl.setPlaybackSpeed(_playbackSpeed);
      ctrl.setVolume(_isMuted ? 0.0 : 1.0);

      if (!mounted) {
        ctrl.dispose();
        _initializingIndices.remove(idx);
        return;
      }

      final currentTarget = <int>{
        if (_focusedIndex - 1 >= 0) _focusedIndex - 1,
        _focusedIndex,
        _focusedIndex + 1,
      };

      if (!currentTarget.contains(idx)) {
        ctrl.dispose();
        _initializingIndices.remove(idx);
        return;
      }

      final playerId = 'feed_${item.id}';
      ref.read(videoPlayerManagerProvider).registerPlayer(
        id: playerId,
        controller: ctrl,
        onPauseRequested: () {
          if (mounted) setState(() {});
        },
      );

      // Reprise de position si existante
      if (item.watchProgressSeconds > 0 &&
          item.durationSeconds > 0 &&
          item.watchProgressSeconds < (item.durationSeconds - 2)) {
        await ctrl.seekTo(Duration(seconds: item.watchProgressSeconds.toInt()));
      }

      // Écouteur pour préchargement anticipé et mode binge automatique
      ctrl.addListener(() {
        if (!mounted || _focusedIndex != idx) return;
        final pos = ctrl.value.position;
        final dur = ctrl.value.duration;

        // Préchargement anticipé de l'épisode suivant 8s avant la fin
        if (dur > Duration.zero && pos >= dur - const Duration(seconds: 8)) {
          final feedState = _getFeedState();
          _preloadNextController(feedState.items);
        }

        // Fin de l'épisode : passage immédiat au suivant
        if (dur > Duration.zero && pos >= dur - const Duration(milliseconds: 500) && !ctrl.value.isPlaying) {
          _onVideoEnded();
        }
      });

      _controllerPool[idx] = ctrl;
      _initializingIndices.remove(idx);

      if (mounted) setState(() {});

      if (idx == _focusedIndex && widget.isActive && _isAppActive) {
        await ref.read(videoPlayerManagerProvider).play(playerId);
        final feedState = _getFeedState();
        _attachWatchdog(_focusedIndex, feedState.items);
      }
    } catch (_) {
      _initializingIndices.remove(idx);
    }
  }

  void _onVideoEnded() {
    final user = ref.read(authProvider).user;
    final watchGate = ref.read(watchGateProvider);
    if ((watchGate.isGateLocked || _isGateLockedLocally) && !watchGate.isUserExempt(user)) {
      _triggerAdGate();
      return;
    }

    final feedState = _getFeedState();
    if (_focusedIndex < feedState.items.length - 1) {
      // Binge automatique immédiat vers l'épisode suivant !
      _pageController.nextPage(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      // Fin de série : afficher la carte de recommandations
      if (widget.seriesId != null || (_customPlaylistItems != null && _customPlaylistItems!.length > 1)) {
        _pageController.nextPage(
          duration: const Duration(milliseconds: 350),
          curve: Curves.easeInOut,
        );
      } else {
        final ctrl = _controllerPool[_focusedIndex];
        ctrl?.seekTo(Duration.zero);
        ctrl?.play();
      }
    }
  }

  void _togglePlayPause() {
    final user = ref.read(authProvider).user;
    final watchGate = ref.read(watchGateProvider);
    if ((watchGate.isGateLocked || _isGateLockedLocally) && !watchGate.isUserExempt(user)) {
      _triggerAdGate();
      return;
    }

    final ctrl = _controllerPool[_focusedIndex];
    if (ctrl == null || !ctrl.value.isInitialized) return;

    final feedState = _getFeedState();
    if (_focusedIndex >= feedState.items.length) return;
    final item = feedState.items[_focusedIndex];
    final playerId = 'feed_${item.id}';

    if (ctrl.value.isPlaying) {
      ref.read(videoPlayerManagerProvider).pause(playerId);
      _watchdog?.setPlaybackDesired(false);
    } else {
      ref.read(videoPlayerManagerProvider).play(playerId);
      _watchdog?.setPlaybackDesired(true);
    }
    setState(() {});
  }

  void _toggleMute() {
    setState(() {
      _isMuted = !_isMuted;
      for (final ctrl in _controllerPool.values) {
        ctrl.setVolume(_isMuted ? 0.0 : 1.0);
      }
    });
  }

  void _handleDoubleTap(TapDownDetails details, FeedItemModel item) {
    setState(() {
      _heartPosition = details.localPosition;
      _showHeartAnimation = true;
    });

    final notifier = widget.seriesId != null
        ? ref.read(seriesFeedNotifierProvider(widget.seriesId!).notifier)
        : ref.read(feedNotifierProvider.notifier);
    notifier.toggleFavorite(item.id);

    final videoModel = VideoModel(
      id: item.id,
      telegramMessageId: item.telegramMessageId,
      title: item.title,
      category: item.category,
      durationSeconds: item.durationSeconds,
      fileSizeBytes: item.fileSizeBytes,
      mimeType: item.mimeType,
      thumbnailPath: item.thumbnailPath,
      viewsCount: item.viewsCount,
      isFavorite: !item.isFavorite,
      watchProgressSeconds: item.watchProgressSeconds,
      isCompleted: item.isCompleted,
    );
    ref.read(favoritesProvider.notifier).toggleFavorite(videoModel);

    Future.delayed(const Duration(milliseconds: 700), () {
      if (mounted) setState(() => _showHeartAnimation = false);
    });
  }

  void _showSpeedPickerModal(AppLocalizations l10n) {
    HapticFeedback.mediumImpact();
    final speeds = [0.75, 1.0, 1.25, 1.5, 2.0];

    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.darkSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  l10n.playbackSpeed,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                ...speeds.map((s) {
                  final isSelected = (_playbackSpeed == s);
                  return ListTile(
                    leading: Icon(
                      isSelected ? Icons.check_circle : Icons.circle_outlined,
                      color: isSelected ? AppTheme.netflixRed : Colors.white54,
                    ),
                    title: Text(
                      '${s}x ${s == 1.0 ? "(Normale)" : ""}',
                      style: TextStyle(
                        color: isSelected ? Colors.white : Colors.white70,
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      ),
                    ),
                    onTap: () {
                      setState(() {
                        _playbackSpeed = s;
                        for (final ctrl in _controllerPool.values) {
                          ctrl.setPlaybackSpeed(s);
                        }
                      });
                      Navigator.pop(context);
                    },
                  );
                }),
              ],
            ),
          ),
        );
      },
    );
  }

  void _showEpisodesBottomSheet(FeedItemModel currentItem, AppLocalizations l10n) {
    final effectiveSeriesId = currentItem.seriesId ?? widget.seriesId;
    if (effectiveSeriesId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Cette vidéo est un contenu autonome.')),
      );
      return;
    }

    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.darkBackground,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return DraggableScrollableSheet(
          initialChildSize: 0.65,
          minChildSize: 0.4,
          maxChildSize: 0.9,
          expand: false,
          builder: (context, scrollController) {
            return Consumer(
              builder: (context, ref, _) {
                final seriesDetailAsync = ref.watch(seriesDetailProvider(effectiveSeriesId));

                return Column(
                  children: [
                    Container(
                      margin: const EdgeInsets.symmetric(vertical: 12),
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.white24,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              currentItem.seriesTitle ?? l10n.episodesList,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close, color: Colors.white70),
                            onPressed: () => Navigator.pop(context),
                          ),
                        ],
                      ),
                    ),
                    const Divider(color: Colors.white12, height: 1),
                    Expanded(
                      child: seriesDetailAsync.when(
                        loading: () => const Center(
                          child: CircularProgressIndicator(color: AppTheme.netflixRed),
                        ),
                        error: (e, _) => Center(
                          child: Text(
                            'Erreur : $e',
                            style: const TextStyle(color: Colors.white60),
                          ),
                        ),
                        data: (series) {
                          if (series == null || series.seasons.isEmpty) {
                            return const Center(
                              child: Text(
                                'Aucun épisode trouvé.',
                                style: TextStyle(color: Colors.white60),
                              ),
                            );
                          }

                          final allEpisodes = series.seasons.expand((s) => s.episodes).toList();

                          return ListView.builder(
                            controller: scrollController,
                            padding: const EdgeInsets.all(16),
                            itemCount: allEpisodes.length,
                            itemBuilder: (context, idx) {
                              final ep = allEpisodes[idx];
                              final isCurrent = (ep.telegramVideoId == currentItem.id);

                              return Container(
                                margin: const EdgeInsets.only(bottom: 12),
                                decoration: BoxDecoration(
                                  color: isCurrent
                                      ? AppTheme.netflixRed.withValues(alpha: 0.15)
                                      : AppTheme.darkSurface,
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(
                                    color: isCurrent
                                        ? AppTheme.netflixRed
                                        : Colors.white.withValues(alpha: 0.08),
                                    width: isCurrent ? 1.5 : 1,
                                  ),
                                ),
                                child: ListTile(
                                  contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                                  leading: Container(
                                    width: 36,
                                    height: 36,
                                    decoration: BoxDecoration(
                                      color: isCurrent ? AppTheme.netflixRed : Colors.white12,
                                      shape: BoxShape.circle,
                                    ),
                                    child: Center(
                                      child: Text(
                                        '${ep.number}',
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                    ),
                                  ),
                                  title: Text(
                                    ep.titleFr ?? 'Épisode ${ep.number}',
                                    style: TextStyle(
                                      color: isCurrent ? Colors.white : Colors.white.withValues(alpha: 0.9),
                                      fontWeight: isCurrent ? FontWeight.bold : FontWeight.w500,
                                    ),
                                  ),
                                  subtitle: Text(
                                    '${ep.durationSec ~/ 60}m',
                                    style: const TextStyle(color: Colors.white54, fontSize: 12),
                                  ),
                                  trailing: isCurrent
                                      ? const Icon(Icons.equalizer_rounded, color: AppTheme.netflixRed)
                                      : const Icon(Icons.play_arrow_rounded, color: Colors.white38),
                                  onTap: () {
                                    Navigator.pop(context);
                                    final feedState = _getFeedState();
                                    final targetIndex = feedState.items.indexWhere(
                                      (it) => it.id == ep.telegramVideoId,
                                    );
                                    if (targetIndex != -1) {
                                      _pageController.animateToPage(
                                        targetIndex,
                                        duration: const Duration(milliseconds: 300),
                                        curve: Curves.easeInOut,
                                      );
                                    } else {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(content: Text('Chargement de l\'épisode...')),
                                      );
                                    }
                                  },
                                ),
                              );
                            },
                          );
                        },
                      ),
                    ),
                  ],
                );
              },
            );
          },
        );
      },
    );
  }

  // =========================================================================
  // Carte « Série terminée » & Recommandations
  // =========================================================================

  Widget _buildEndOfSeriesCard(BuildContext context, AppLocalizations l10n, String baseUrl) {
    final seriesListAsync = ref.watch(seriesListProvider);

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Dégradé de fond sombre et immersif
          Container(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(0, -0.3),
                radius: 1.2,
                colors: [
                  Color(0xFF221215),
                  Colors.black,
                ],
              ),
            ),
          ),

          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(height: 30),
                  // Icône de célébration / complétion
                  Container(
                    width: 76,
                    height: 76,
                    decoration: BoxDecoration(
                      color: AppTheme.netflixRed.withValues(alpha: 0.2),
                      shape: BoxShape.circle,
                      border: Border.all(color: AppTheme.netflixRed, width: 2.5),
                    ),
                    child: const Icon(
                      Icons.check_circle_rounded,
                      color: AppTheme.netflixRed,
                      size: 46,
                    ),
                  ),
                  const SizedBox(height: 18),
                  Text(
                    l10n.seriesCompletedTitle,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    l10n.seriesCompletedSubtitle,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 14,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 32),

                  // Séries recommandées
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      l10n.recommendedSeries,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),

                  seriesListAsync.when(
                    loading: () => const Center(
                      child: CircularProgressIndicator(color: AppTheme.netflixRed),
                    ),
                    error: (_, __) => const SizedBox.shrink(),
                    data: (seriesList) {
                      final filtered = seriesList
                          .where((s) => s.id != widget.seriesId)
                          .take(3)
                          .toList();

                      if (filtered.isEmpty) return const SizedBox.shrink();

                      return Column(
                        children: filtered.map((rec) {
                          final posterUrl = ImageUtils.resolveUrl(rec.posterPath, baseUrl);
                          return Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            decoration: BoxDecoration(
                              color: AppTheme.darkSurface,
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: Colors.white10),
                            ),
                            child: ListTile(
                              contentPadding: const EdgeInsets.all(8),
                              leading: ClipRRect(
                                borderRadius: BorderRadius.circular(6),
                                child: posterUrl != null && posterUrl.isNotEmpty
                                    ? CachedNetworkImage(
                                        imageUrl: posterUrl,
                                        width: 50,
                                        height: 70,
                                        fit: BoxFit.cover,
                                        placeholder: (_, __) => Container(color: Colors.black26),
                                        errorWidget: (_, __, ___) => Container(color: Colors.black26),
                                      )
                                    : Container(
                                        width: 50,
                                        height: 70,
                                        color: Colors.white12,
                                        child: const Icon(Icons.movie, color: Colors.white54),
                                      ),
                              ),
                              title: Text(
                                rec.title,
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 14,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              subtitle: Text(
                                rec.genres.isNotEmpty ? rec.genres.join(', ') : 'Série',
                                style: const TextStyle(color: Colors.white54, fontSize: 12),
                                maxLines: 1,
                              ),
                              trailing: ElevatedButton.icon(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppTheme.netflixRed,
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                                ),
                                icon: const Icon(Icons.play_arrow_rounded, color: Colors.white, size: 18),
                                label: const Text(
                                  'Regarder',
                                  style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
                                ),
                                onPressed: () {
                                  // Lancement direct de la série recommandée dans le lecteur vertical
                                  Navigator.pushReplacement(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) => ReelsScreen(
                                        seriesId: rec.id,
                                        isActive: true,
                                        isStandalone: true,
                                      ),
                                    ),
                                  );
                                },
                              ),
                            ),
                          );
                        }).toList(),
                      );
                    },
                  ),

                  const SizedBox(height: 24),
                  // Bouton recommencer la série
                  TouchableScale(
                    onTap: () {
                      _pageController.animateToPage(
                        0,
                        duration: const Duration(milliseconds: 500),
                        curve: Curves.easeInOut,
                      );
                    },
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      decoration: BoxDecoration(
                        color: Colors.white12,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.replay_rounded, color: Colors.white, size: 20),
                          const SizedBox(width: 8),
                          Text(
                            l10n.restartSeries,
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  // Bouton retour à l'accueil
                  TouchableScale(
                    onTap: () {
                      ref.read(videoPlayerManagerProvider).pauseAll();
                      Navigator.pop(context);
                    },
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      decoration: BoxDecoration(
                        color: Colors.transparent,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.white24),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.home_rounded, color: Colors.white70, size: 20),
                          const SizedBox(width: 8),
                          Text(
                            l10n.backToHome,
                            style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),

          // Bouton retour supérieur
          if (widget.isStandalone || Navigator.canPop(context))
            Positioned(
              top: 0,
              left: 0,
              child: SafeArea(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  child: TouchableScale(
                    onTap: () {
                      ref.read(videoPlayerManagerProvider).pauseAll();
                      Navigator.pop(context);
                    },
                    child: Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.5),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white24),
                      ),
                      child: const Icon(
                        Icons.arrow_back_ios_new_rounded,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  // =========================================================================
  // Rendu Principal de l'Interface
  // =========================================================================

  @override
  Widget build(BuildContext context) {
    final feedState = _getFeedState();
    final l10n = context.l10n;
    final user = ref.watch(authProvider).user;
    final watchGate = ref.watch(watchGateProvider);
    final isGateLocked = (watchGate.isGateLocked || _isGateLockedLocally) && !watchGate.isUserExempt(user);

    if (feedState.isLoading) {
      return const Scaffold(
        backgroundColor: Colors.black,
        body: Center(
          child: CircularProgressIndicator(color: AppTheme.netflixRed),
        ),
      );
    }

    if (feedState.error != null && feedState.items.isEmpty) {
      return Scaffold(
        backgroundColor: AppTheme.darkBackground,
        body: Center(
          child: ErrorStateView(
            message: feedState.error!,
            onRetry: () {
              if (widget.seriesId != null) {
                ref.read(seriesFeedNotifierProvider(widget.seriesId!).notifier).loadInitial();
              } else {
                ref.read(feedNotifierProvider.notifier).loadInitial();
              }
            },
          ),
        ),
      );
    }

    if (feedState.items.isEmpty) {
      return Scaffold(
        backgroundColor: AppTheme.darkBackground,
        body: Center(
          child: EmptyStateView(
            icon: Icons.movie_filter_rounded,
            title: l10n.noReelsAvailable,
          ),
        ),
      );
    }

    // Réconciliation initiale si le pool est vide
    if (_controllerPool.isEmpty && feedState.items.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _reconcileControllers(_focusedIndex, feedState.items);
      });
    }

    // Saut initial vers l'épisode spécifié (pour les séries chargées par API)
    if (!_hasJumpedToInitial && widget.initialVideoId != null && feedState.items.isNotEmpty) {
      _hasJumpedToInitial = true;
      final targetIdx = feedState.items.indexWhere((it) => it.id == widget.initialVideoId);
      if (targetIdx > 0) {
        _focusedIndex = targetIdx;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (_pageController.hasClients) {
            _pageController.jumpToPage(targetIdx);
          }
        });
      }
    }

    final hasEndOfSeriesCard = (widget.seriesId != null || (_customPlaylistItems != null && _customPlaylistItems!.length > 1));
    final totalCount = feedState.items.length + (hasEndOfSeriesCard ? 1 : 0);

    return Scaffold(
      backgroundColor: Colors.black,
      body: FutureBuilder<String>(
        future: storageService.getServerUrl(),
        builder: (context, snapshot) {
          final baseUrl = snapshot.data ?? ApiConstants.defaultBaseUrl;

          return PageView.builder(
            controller: _pageController,
            scrollDirection: Axis.vertical,
            physics: isGateLocked
                ? const NeverScrollableScrollPhysics()
                : const PageScrollPhysics(parent: BouncingScrollPhysics()),
            itemCount: totalCount,
            onPageChanged: (newIndex) {
              setState(() {
                _focusedIndex = newIndex;
              });
              if (isGateLocked) {
                _triggerAdGate();
                return;
              }

              if (newIndex < feedState.items.length) {
                _reconcileControllers(newIndex, feedState.items);

                // Pagination curseur pour le flux Découvrir
                if (newIndex >= feedState.items.length - 3 && _customPlaylistItems == null) {
                  if (widget.seriesId != null) {
                    ref.read(seriesFeedNotifierProvider(widget.seriesId!).notifier).loadMore();
                  } else {
                    ref.read(feedNotifierProvider.notifier).loadMore();
                  }
                }
              } else {
                // Page fin de série atteinte
                _videoPlayerManager?.pauseAll();
              }
            },
            itemBuilder: (context, index) {
              // Carte fin de série
              if (index == feedState.items.length) {
                return _buildEndOfSeriesCard(context, l10n, baseUrl);
              }

              final item = feedState.items[index];
              final ctrl = _controllerPool[index];
              final isCurrent = (index == _focusedIndex);
              final isInitialized = ctrl != null && ctrl.value.isInitialized;
              final isPlaying = isInitialized && ctrl.value.isPlaying;
              final isBuffering = isInitialized && ctrl.value.isBuffering;
              final thumbUrl = ImageUtils.resolveUrl(item.thumbnailPath, baseUrl);

              return GestureDetector(
                onTap: _togglePlayPause,
                onDoubleTapDown: (details) => _handleDoubleTap(details, item),
                onLongPress: () => _showSpeedPickerModal(l10n),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    // 1. Miniature d'attente (évite tout écran noir au démarrage)
                    if (thumbUrl != null && thumbUrl.isNotEmpty)
                      CachedNetworkImage(
                        imageUrl: thumbUrl,
                        fit: BoxFit.cover,
                        alignment: Alignment.center,
                        placeholder: (_, __) => Container(color: Colors.black),
                        errorWidget: (_, __, ___) => Container(color: Colors.black),
                      )
                    else
                      Container(color: Colors.black),

                    // 2. Lecteur Vidéo Plein Écran
                    if (isInitialized)
                      Center(
                        child: FittedBox(
                          fit: BoxFit.cover,
                          child: SizedBox(
                            width: ctrl.value.size.width,
                            height: ctrl.value.size.height,
                            child: VideoPlayer(ctrl),
                          ),
                        ),
                      ),

                    // Indicateur de chargement / Buffering discret
                    if (!isInitialized || isBuffering)
                      Center(
                        child: Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.5),
                            shape: BoxShape.circle,
                          ),
                          child: const CircularProgressIndicator(
                            strokeWidth: 2.5,
                            color: AppTheme.netflixRed,
                          ),
                        ),
                      ),

                    // 3. Dégradé sombre cinématique (haut et bas)
                    Positioned.fill(
                      child: Container(
                        decoration: const BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              Color(0x99000000),
                              Colors.transparent,
                              Colors.transparent,
                              Color(0xCC000000),
                            ],
                            stops: [0.0, 0.22, 0.65, 1.0],
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                          ),
                        ),
                      ),
                    ),

                    // 4. Icône centrale lors de la pause
                    if (isInitialized && !isPlaying && isCurrent && !_showingAdGatePrompt && !isGateLocked)
                      Center(
                        child: Container(
                          padding: const EdgeInsets.all(18),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.55),
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white24, width: 1.5),
                          ),
                          child: const Icon(
                            Icons.play_arrow_rounded,
                            color: Colors.white,
                            size: 52,
                          ),
                        ),
                      ),

                    // 5. Cœur animé au double-tap
                    if (_showHeartAnimation)
                      Positioned(
                        left: _heartPosition.dx - 45,
                        top: _heartPosition.dy - 45,
                        child: const Icon(
                          Icons.favorite,
                          color: AppTheme.netflixRed,
                          size: 90,
                          shadows: [
                            Shadow(color: Colors.black54, blurRadius: 16),
                          ],
                        ),
                      ),

                    // 6. Colonne d'actions verticales à droite
                    Positioned(
                      right: 14,
                      bottom: 84,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // A. Favori / Ma liste
                          TouchableScale(
                            onTap: () {
                              final notifier = widget.seriesId != null
                                  ? ref.read(seriesFeedNotifierProvider(widget.seriesId!).notifier)
                                  : ref.read(feedNotifierProvider.notifier);
                              notifier.toggleFavorite(item.id);

                              final videoModel = VideoModel(
                                id: item.id,
                                telegramMessageId: item.telegramMessageId,
                                title: item.title,
                                category: item.category,
                                durationSeconds: item.durationSeconds,
                                fileSizeBytes: item.fileSizeBytes,
                                mimeType: item.mimeType,
                                thumbnailPath: item.thumbnailPath,
                                viewsCount: item.viewsCount,
                                isFavorite: !item.isFavorite,
                                watchProgressSeconds: item.watchProgressSeconds,
                                isCompleted: item.isCompleted,
                              );
                              ref.read(favoritesProvider.notifier).toggleFavorite(videoModel);
                            },
                            child: Column(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: Colors.black.withValues(alpha: 0.45),
                                    shape: BoxShape.circle,
                                    border: Border.all(color: Colors.white12),
                                  ),
                                  child: Icon(
                                    item.isFavorite ? Icons.favorite_rounded : Icons.favorite_border_rounded,
                                    color: item.isFavorite ? AppTheme.netflixRed : Colors.white,
                                    size: 28,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  '${item.viewsCount}',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                    shadows: [Shadow(color: Colors.black, blurRadius: 4)],
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),

                          // B. Liste des épisodes
                          TouchableScale(
                            onTap: () => _showEpisodesBottomSheet(item, l10n),
                            child: Column(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: Colors.black.withValues(alpha: 0.45),
                                    shape: BoxShape.circle,
                                    border: Border.all(color: Colors.white12),
                                  ),
                                  child: const Icon(
                                    Icons.video_library_rounded,
                                    color: Colors.white,
                                    size: 26,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  l10n.episodesList,
                                  style: const TextStyle(
                                    color: Colors.white70,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                    shadows: [Shadow(color: Colors.black, blurRadius: 4)],
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),

                          // C. Vitesse de lecture
                          TouchableScale(
                            onTap: () => _showSpeedPickerModal(l10n),
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                              decoration: BoxDecoration(
                                color: Colors.black.withValues(alpha: 0.5),
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(color: Colors.white24),
                              ),
                              child: Text(
                                '${_playbackSpeed}x',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),

                          // D. Mute / Démute
                          TouchableScale(
                            onTap: _toggleMute,
                            child: Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: Colors.black.withValues(alpha: 0.45),
                                shape: BoxShape.circle,
                                border: Border.all(color: Colors.white12),
                              ),
                              child: Icon(
                                _isMuted ? Icons.volume_off_rounded : Icons.volume_up_rounded,
                                color: Colors.white,
                                size: 24,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),

                    // 7. Métadonnées textuelles en bas à gauche
                    Positioned(
                      left: 16,
                      bottom: 40,
                      right: 84,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (item.seriesTitle != null)
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: AppTheme.netflixRed,
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    'S${item.seasonNumber} : E${item.episodeNumber}',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    item.seriesTitle!,
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 15,
                                      fontWeight: FontWeight.bold,
                                      shadows: [Shadow(color: Colors.black, blurRadius: 6)],
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ],
                            ),
                          const SizedBox(height: 6),
                          Text(
                            item.episodeTitle ?? item.title,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              shadows: [Shadow(color: Colors.black, blurRadius: 4)],
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          if (item.caption != null && item.caption!.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              item.caption!,
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 12,
                                shadows: [Shadow(color: Colors.black, blurRadius: 4)],
                              ),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ],
                      ),
                    ),

                    // 8. Barre fine de scrubbing rouge au bas de l'écran
                    if (isInitialized)
                      Positioned(
                        left: 0,
                        right: 0,
                        bottom: 0,
                        child: ValueListenableBuilder<VideoPlayerValue>(
                          valueListenable: ctrl,
                          builder: (context, val, _) {
                            final durationMs = val.duration.inMilliseconds;
                            final positionMs = val.position.inMilliseconds;
                            final progress = durationMs > 0 ? (positionMs / durationMs).clamp(0.0, 1.0) : 0.0;

                            return LinearProgressIndicator(
                              value: progress,
                              backgroundColor: Colors.white12,
                              valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.netflixRed),
                              minHeight: 2.5,
                            );
                          },
                        ),
                      ),

                    // 9. Écran de verrouillage publicitaire AdGate
                    if (isCurrent && isGateLocked)
                      Positioned.fill(
                        child: AdGateLockedOverlay(
                          onWatchAd: _launchRewardedAd,
                          onBack: () {
                            if (Navigator.canPop(context)) {
                              Navigator.pop(context);
                            }
                          },
                        ),
                      ),

                    // 10. Bouton retour supérieur gauche (si standalone ou navigable en arrière)
                    if (widget.isStandalone || Navigator.canPop(context))
                      Positioned(
                        top: 0,
                        left: 0,
                        child: SafeArea(
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                            child: TouchableScale(
                              onTap: () {
                                ref.read(videoPlayerManagerProvider).pauseAll();
                                Navigator.pop(context);
                              },
                              child: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Colors.black.withValues(alpha: 0.5),
                                  shape: BoxShape.circle,
                                  border: Border.all(color: Colors.white24),
                                ),
                                child: const Icon(
                                  Icons.arrow_back_ios_new_rounded,
                                  color: Colors.white,
                                  size: 20,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              );
            },
          );
        },
      ),
    );
  }
}
