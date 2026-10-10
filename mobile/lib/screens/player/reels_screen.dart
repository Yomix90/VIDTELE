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
import 'video_player_screen.dart';

/// Écran de flux vertical d'épisodes et vidéos façon TikTok / ReelShort / DramaBox.
/// Caractéristiques techniques majeures :
/// - PageView vertical plein écran avec snap fluide
/// - Pool strict de MAX 3 contrôleurs vidéo (focused - 1, focused, focused + 1)
/// - Libération immédiate de la mémoire dès qu'un contrôleur quitte les 3 cibles
/// - Préchargement anticipé du contrôleur suivant
/// - Démarrage rapide avec miniature d'attente sans écran noir
/// - Mode binge automatique en fin d'épisode
/// - Feuille d'épisodes de la série (Bottom Sheet)
/// - Sélecteur de vitesse de lecture et double-tap favori
class ReelsScreen extends ConsumerStatefulWidget {
  final bool isActive;
  final int? seriesId;
  final int? initialVideoId;

  const ReelsScreen({
    super.key,
    this.isActive = true,
    this.seriesId,
    this.initialVideoId,
  });

  @override
  ConsumerState<ReelsScreen> createState() => _ReelsScreenState();
}

class _ReelsScreenState extends ConsumerState<ReelsScreen> with WidgetsBindingObserver {
  late final PageController _pageController;
  int _focusedIndex = 0;
  bool _isAppActive = true;
  double _playbackSpeed = 1.0;
  bool _isMuted = false;

  // Pool de contrôleurs limité à MAX 3 en mémoire
  final Map<int, VideoPlayerController> _controllerPool = {};
  final Set<int> _initializingIndices = {};

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
    _pageController = PageController();
    _startProgressSyncTimer();
  }

  @override
  void didUpdateWidget(covariant ReelsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.isActive && oldWidget.isActive) {
      // Coupure immédiate du son et du timer quand on quitte l'onglet Découvrir
      _progressSyncTimer?.cancel();
      _progressSyncTimer = null;
      _videoPlayerManager?.pauseAll();
    } else if (widget.isActive && !oldWidget.isActive) {
      // Reprise de la vidéo visible et du timer
      _startProgressSyncTimer();
      final feedState = _getFeedState();
      _reconcileControllers(_focusedIndex, feedState.items);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _isAppActive = false;
      _progressSyncTimer?.cancel();
      _progressSyncTimer = null;
      _videoPlayerManager?.pauseAll();
    } else if (state == AppLifecycleState.resumed) {
      _isAppActive = true;
      if (widget.isActive) {
        _startProgressSyncTimer();
        final feedState = _getFeedState();
        _reconcileControllers(_focusedIndex, feedState.items);
      }
    }
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _progressSyncTimer?.cancel();
    _progressSyncTimer = null;

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
    return widget.seriesId != null
        ? ref.read(seriesFeedNotifierProvider(widget.seriesId!))
        : ref.read(feedNotifierProvider);
  }

  /// Vérifie si la progression de la vidéo déclenche le verrou de publicité récompensée
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

  /// Met en pause et présente la demande de consentement à la pub récompensée
  void _triggerAdGate() {
    if (_showingAdGatePrompt || !mounted) return;
    _showingAdGatePrompt = true;

    // Coupure immédiate du lecteur vertical
    final ctrl = _controllerPool[_focusedIndex];
    ctrl?.pause();
    _videoPlayerManager?.pauseAll();

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

  /// Déclenche l'affichage plein écran de l'annonce avec récompense AdMob
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
            // Reprendre la vidéo visible
            final feedState = _getFeedState();
            if (_focusedIndex < feedState.items.length) {
              final vidId = feedState.items[_focusedIndex].id;
              _videoPlayerManager?.play('feed_$vidId');
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
                  }
                },
              ),
            ),
          );
        }
      },
    );

    if (!success) {
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
                }
              },
            ),
          ),
        );
      }
    }
  }

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

  /// Réconciliation stricte du pool de contrôleurs : MAX 3 contrôleurs en mémoire
  void _reconcileControllers(int currentIndex, List<FeedItemModel> items) {
    if (items.isEmpty) return;

    // 1. Les 3 indices cibles autorisés
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
        } else {
          ref.read(videoPlayerManagerProvider).pause(playerId);
        }
      }
    }
  }

  Future<void> _initControllerForIndex(int idx, FeedItemModel item) async {
    _initializingIndices.add(idx);

    try {
      final baseUrl = await storageService.getServerUrl();
      final accessToken = await storageService.getAccessToken();

      String? streamToken;
      try {
        final tokenRes = await apiClient.dio.post(
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

      // Vérifier que cet index est toujours dans la fenêtre des 3 cibles
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

      // Écouteur de fin de vidéo pour le mode binge
      ctrl.addListener(() {
        if (!mounted || _focusedIndex != idx) return;
        final pos = ctrl.value.position;
        final dur = ctrl.value.duration;
        if (dur > Duration.zero && pos >= dur && !ctrl.value.isPlaying) {
          _onVideoEnded();
        }
      });

      _controllerPool[idx] = ctrl;
      _initializingIndices.remove(idx);

      if (mounted) setState(() {});

      if (idx == _focusedIndex && widget.isActive && _isAppActive) {
        await ref.read(videoPlayerManagerProvider).play(playerId);
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
      // Binge automatique : passage à l'épisode suivant !
      _pageController.nextPage(
        duration: const Duration(milliseconds: 450),
        curve: Curves.easeInOutCubic,
      );
    } else {
      // Rebouclage si fin du catalogue
      final ctrl = _controllerPool[_focusedIndex];
      ctrl?.seekTo(Duration.zero);
      ctrl?.play();
    }
  }

  void _skipToNextEpisode() {
    final user = ref.read(authProvider).user;
    final watchGate = ref.read(watchGateProvider);
    if ((watchGate.isGateLocked || _isGateLockedLocally) && !watchGate.isUserExempt(user)) {
      _triggerAdGate();
      return;
    }

    final feedState = _getFeedState();
    if (_focusedIndex < feedState.items.length - 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeOutCubic,
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Dernier épisode atteint.'),
          duration: Duration(seconds: 2),
        ),
      );
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
    } else {
      ref.read(videoPlayerManagerProvider).play(playerId);
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

    // Basculer l'état favori
    final notifier = widget.seriesId != null
        ? ref.read(seriesFeedNotifierProvider(widget.seriesId!).notifier)
        : ref.read(feedNotifierProvider.notifier);
    notifier.toggleFavorite(item.id);

    // Synchronisation avec le provider global
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
    if (currentItem.seriesId == null) {
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
                final seriesDetailAsync = ref.watch(seriesDetailProvider(currentItem.seriesId!));

                return Column(
                  children: [
                    // Barre de poignée
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
                                    // Trouver l'index correspondant dans les éléments du feed
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

  void _shareItem(FeedItemModel item, AppLocalizations l10n) async {
    final baseUrl = await storageService.getServerUrl();
    final shareUrl = '$baseUrl/series/${item.seriesId ?? item.id}';

    await Clipboard.setData(ClipboardData(text: shareUrl));
    HapticFeedback.lightImpact();

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check_circle, color: Colors.white, size: 20),
              const SizedBox(width: 8),
              Text(l10n.linkCopied),
            ],
          ),
          backgroundColor: AppTheme.darkSurface,
          behavior: SnackBarBehavior.floating,
          duration: const Duration(seconds: 2),
        ),
      );
    }
  }

  void _openLandscapePlayer(FeedItemModel item) {
    ref.read(videoPlayerManagerProvider).pauseAll();

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
      isFavorite: item.isFavorite,
      watchProgressSeconds: item.watchProgressSeconds,
      isCompleted: item.isCompleted,
      seasonNumber: item.seasonNumber,
      episodeNumber: item.episodeNumber,
      episodeTitle: item.episodeTitle,
    );

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => VideoPlayerScreen(video: videoModel),
      ),
    ).then((_) {
      // Reprise au retour
      if (mounted && widget.isActive) {
        final feedState = _getFeedState();
        _reconcileControllers(_focusedIndex, feedState.items);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final feedState = widget.seriesId != null
        ? ref.watch(seriesFeedNotifierProvider(widget.seriesId!))
        : ref.watch(feedNotifierProvider);
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

    // Déclencher la réconciliation initiale si le pool est vide
    if (_controllerPool.isEmpty && feedState.items.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _reconcileControllers(_focusedIndex, feedState.items);
      });
    }

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
            itemCount: feedState.items.length,
            onPageChanged: (newIndex) {
              setState(() {
                _focusedIndex = newIndex;
              });
              if (isGateLocked) {
                _triggerAdGate();
                return;
              }
              _reconcileControllers(newIndex, feedState.items);

              // Pagination par curseur quand on approche de la fin du flux
              if (newIndex >= feedState.items.length - 3) {
                if (widget.seriesId != null) {
                  ref.read(seriesFeedNotifierProvider(widget.seriesId!).notifier).loadMore();
                } else {
                  ref.read(feedNotifierProvider.notifier).loadMore();
                }
              }
            },
            itemBuilder: (context, index) {
              final item = feedState.items[index];
              final ctrl = _controllerPool[index];
              final isCurrent = (index == _focusedIndex);
              final isInitialized = ctrl != null && ctrl.value.isInitialized;
              final isPlaying = isInitialized && ctrl.value.isPlaying;
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
                      )
                    else
                      // Indicateur discret de préchargement
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
                    if (isInitialized && !isPlaying && isCurrent)
                      Center(
                        child: Container(
                          padding: const EdgeInsets.all(18),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.6),
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white30, width: 1.5),
                          ),
                          child: const Icon(
                            Icons.play_arrow_rounded,
                            size: 54,
                            color: Colors.white,
                          ),
                        ),
                      ),

                    // 5. Animation d'éclat du Cœur (Double-Tap)
                    if (_showHeartAnimation && isCurrent)
                      Positioned(
                        left: _heartPosition.dx - 45,
                        top: _heartPosition.dy - 45,
                        child: TweenAnimationBuilder<double>(
                          tween: Tween(begin: 0.6, end: 1.3),
                          duration: const Duration(milliseconds: 500),
                          curve: Curves.elasticOut,
                          builder: (context, scale, child) {
                            return Transform.scale(
                              scale: scale,
                              child: const Icon(
                                Icons.favorite,
                                color: AppTheme.netflixRed,
                                size: 90,
                                shadows: [
                                  Shadow(color: Colors.black, blurRadius: 16),
                                ],
                              ),
                            );
                          },
                        ),
                      ),

                    // 6. Colonne d'actions TikTok à droite
                    Positioned(
                      right: 12,
                      bottom: 70,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // A. Favori / Cœur
                          Consumer(
                            builder: (context, ref, _) {
                              final favorites = ref.watch(favoritesProvider).value ?? [];
                              final isFav = favorites.any((v) => v.id == item.id) || item.isFavorite;

                              return TouchableScale(
                                onTap: () {
                                  ref.read(feedNotifierProvider.notifier).toggleFavorite(item.id);
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
                                    isFavorite: !isFav,
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
                                        isFav ? Icons.favorite : Icons.favorite_border,
                                        color: isFav ? AppTheme.netflixRed : Colors.white,
                                        size: 28,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      isFav ? '1' : '0',
                                      style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        shadows: [Shadow(color: Colors.black, blurRadius: 4)],
                                      ),
                                    ),
                                  ],
                                ),
                              );
                            },
                          ),
                          const SizedBox(height: 16),

                          // B. Liste des Épisodes (Bottom sheet)
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
                                    Icons.playlist_play_rounded,
                                    color: Colors.white,
                                    size: 28,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                const Text(
                                  'Épisodes',
                                  style: TextStyle(
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

                          // C. Épisode Suivant (Bouton d'enchaînement direct)
                          TouchableScale(
                            onTap: _skipToNextEpisode,
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
                                    Icons.skip_next_rounded,
                                    color: Colors.white,
                                    size: 28,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  l10n.nextEpisode,
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

                          // D. Plein écran Paysage
                          TouchableScale(
                            onTap: () => _openLandscapePlayer(item),
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
                                    Icons.fullscreen_rounded,
                                    color: Colors.white,
                                    size: 28,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                const Text(
                                  'Plein écran',
                                  style: TextStyle(
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

                          // E. Vitesse de lecture
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

                          // F. Mute / Démute
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
                          const SizedBox(height: 16),

                          // G. Partager
                          TouchableScale(
                            onTap: () => _shareItem(item, l10n),
                            child: Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: Colors.black.withValues(alpha: 0.45),
                                shape: BoxShape.circle,
                                border: Border.all(color: Colors.white12),
                              ),
                              child: const Icon(
                                Icons.share_rounded,
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
                      right: 90,
                      bottom: 24,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // Badge Série ou Catégorie
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
                            decoration: BoxDecoration(
                              color: AppTheme.netflixRed.withValues(alpha: 0.9),
                              borderRadius: BorderRadius.circular(4),
                              boxShadow: [
                                BoxShadow(
                                  color: AppTheme.netflixRed.withValues(alpha: 0.4),
                                  blurRadius: 6,
                                ),
                              ],
                            ),
                            child: Text(
                              (item.seriesTitle != null && item.seriesTitle!.isNotEmpty)
                                  ? item.seriesTitle!.toUpperCase()
                                  : item.category.toUpperCase(),
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w900,
                                letterSpacing: 1.2,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(height: 8),

                          // Titre principal de l'épisode
                          Text(
                            item.displayHeadline,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 0.2,
                              shadows: [
                                Shadow(color: Colors.black, blurRadius: 6, offset: Offset(0, 1)),
                              ],
                            ),
                          ),

                          // Synopsis ou description
                          if (item.caption != null && item.caption!.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              item.caption!,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.8),
                                fontSize: 12,
                                height: 1.3,
                                shadows: const [
                                  Shadow(color: Colors.black, blurRadius: 4, offset: Offset(0, 1)),
                                ],
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),

                    // 8. Barre de progression fine au bas de l'écran
                    if (isInitialized)
                      Positioned(
                        left: 0,
                        right: 0,
                        bottom: 0,
                        child: VideoProgressIndicator(
                          ctrl,
                          allowScrubbing: true,
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          colors: const VideoProgressColors(
                            playedColor: AppTheme.netflixRed,
                            bufferedColor: Colors.white24,
                            backgroundColor: Colors.transparent,
                          ),
                        ),
                      ),

                    // 9. Overlay de verrouillage AdGate si quota atteint et non exempté
                    if (isCurrent && isGateLocked && !_showingAdGatePrompt)
                      Positioned.fill(
                        child: AdGateLockedOverlay(
                          onWatchAd: _launchRewardedAd,
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
