import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';
import 'package:chewie/chewie.dart';
import 'package:dio/dio.dart';

import '../../core/ads/rewarded_ad_service.dart';
import '../../core/ads/watch_gate_controller.dart';
import '../../core/api/api_client.dart';
import '../../core/constants/api_constants.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/navigation/app_route_observer.dart';
import '../../core/services/video_player_manager.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../models/video_model.dart';
import '../../providers/auth_provider.dart';
import '../../providers/library_provider.dart';
import '../../widgets/ad_gate_locked_overlay.dart';
import '../../widgets/ad_gate_prompt_sheet.dart';

/// Lecteur vidéo immersif Netflix-style avec streaming HTTP 206 partiel,
/// reprise automatique de lecture, synchronisation de l'historique,
/// maintien de l'écran allumé (Wakelock), coupure audio en arrière-plan,
/// et enchaînement automatique des épisodes (Auto-play next).
class VideoPlayerScreen extends ConsumerStatefulWidget {
  final VideoModel video;
  final List<VideoModel>? playlist;
  final int? initialIndex;

  const VideoPlayerScreen({
    super.key,
    required this.video,
    this.playlist,
    this.initialIndex,
  });

  @override
  ConsumerState<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends ConsumerState<VideoPlayerScreen>
    with WidgetsBindingObserver, RouteAware {
  late VideoModel _currentVideo;
  late int _currentIndex;
  late List<VideoModel> _playlist;

  VideoPlayerController? _videoPlayerController;
  ChewieController? _chewieController;

  bool _isLoading = true;
  int? _errorCode;
  String? _customError;
  Timer? _progressTimer;
  bool _isDisposed = false;

  String get _playerId => 'player_${_currentVideo.id}';

  Timer? _autoNextTimer;
  int _countdownSeconds = 5;
  bool _showingNextPrompt = false;

  // Contrôle de quota AdGate
  bool _showingAdGatePrompt = false;
  bool _isGateLockedLocally = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);

    _currentVideo = widget.video;
    _playlist = widget.playlist ?? [widget.video];
    _currentIndex = widget.initialIndex ?? _playlist.indexWhere((v) => v.id == widget.video.id);
    if (_currentIndex < 0) _currentIndex = 0;

    _initPlayer();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final route = ModalRoute.of(context);
    if (route != null) {
      appRouteObserver.subscribe(this, route);
    }
  }

  @override
  void didPushNext() {
    // Si une nouvelle route (écran, dialog, modal) est ouverte au-dessus du lecteur, pause immédiate
    ref.read(videoPlayerManagerProvider).pause(_playerId);
    super.didPushNext();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      // Coupure immédiate du son et de l'image dès que l'application quitte le premier plan
      ref.read(videoPlayerManagerProvider).pauseAll();
    }
  }

  bool get _hasNextVideo => _currentIndex + 1 < _playlist.length;
  bool get _hasPreviousVideo => _currentIndex > 0;
  VideoModel? get _nextVideo => _hasNextVideo ? _playlist[_currentIndex + 1] : null;

  /// Initialisation du contrôleur vidéo et du streaming sécurisé
  Future<void> _initPlayer() async {
    _autoNextTimer?.cancel();

    // 0. Vérification du quota AdGate avant initialisation du streaming
    final user = ref.read(authProvider).user;
    final watchGate = ref.read(watchGateProvider);
    if (watchGate.isGateLocked && !watchGate.isUserExempt(user)) {
      setState(() {
        _isLoading = false;
        _isGateLockedLocally = true;
      });
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _triggerAdGate();
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorCode = null;
      _customError = null;
      _showingNextPrompt = false;
      _countdownSeconds = 5;
    });

    try {
      final baseUrl = await storageService.getServerUrl();
      final accessToken = await storageService.getAccessToken();

      // 1. Obtention d'un jeton de streaming dédié ou fallback accessToken
      String? streamToken;
      try {
        final tokenRes = await apiClient.dio.post(
          ApiConstants.videoStreamToken(_currentVideo.id),
        );
        streamToken = tokenRes.data['stream_token'];
      } catch (e) {
        streamToken = accessToken;
      }

      if (streamToken == null) {
        throw Exception("Auth token missing");
      }

      // 2. Construction de l'URL de streaming avec jeton
      final streamUri = Uri.parse(
        '$baseUrl${ApiConstants.videoStream(_currentVideo.id)}?token=$streamToken',
      );

      // 3. Initialisation du contrôleur natif
      final controller = VideoPlayerController.networkUrl(
        streamUri,
        httpHeaders: {
          if (accessToken != null) 'Authorization': 'Bearer $accessToken',
        },
      );

      await controller.initialize();

      if (_isDisposed) {
        controller.dispose();
        return;
      }

      // Activer l'écouteur de fin de vidéo et wakelock
      controller.addListener(_onVideoControllerUpdate);

      // 4. Reprise automatique à la dernière position connue (si non terminée)
      if (_currentVideo.watchProgressSeconds > 0 && !_currentVideo.isCompleted) {
        final resumePosition = Duration(seconds: _currentVideo.watchProgressSeconds.toInt());
        if (resumePosition < controller.value.duration) {
          await controller.seekTo(resumePosition);
        }
      }

      // 5. Configuration de Chewie (style Netflix)
      final chewie = ChewieController(
        videoPlayerController: controller,
        autoPlay: true,
        looping: false,
        allowFullScreen: true,
        allowMuting: true,
        allowPlaybackSpeedChanging: true,
        playbackSpeeds: const [0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
        materialProgressColors: ChewieProgressColors(
          playedColor: AppTheme.netflixRed,
          handleColor: AppTheme.netflixRed,
          bufferedColor: Colors.white24,
          backgroundColor: Colors.white12,
        ),
        cupertinoProgressColors: ChewieProgressColors(
          playedColor: AppTheme.netflixRed,
          handleColor: AppTheme.netflixRed,
          bufferedColor: Colors.white24,
          backgroundColor: Colors.white12,
        ),
        placeholder: Container(
          color: Colors.black,
          child: const Center(
            child: CircularProgressIndicator(color: AppTheme.netflixRed),
          ),
        ),
        errorBuilder: (context, errorMessage) {
          final l10n = context.l10n;
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.error_outline, color: Colors.redAccent, size: 54),
                  const SizedBox(height: 16),
                  Text(
                    '${l10n.playbackErrorTitle} : $errorMessage',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 16),
                  ),
                  const SizedBox(height: 20),
                  ElevatedButton(
                    onPressed: _initPlayer,
                    style: ElevatedButton.styleFrom(backgroundColor: AppTheme.netflixRed),
                    child: Text(l10n.retry),
                  ),
                ],
              ),
            ),
          );
        },
      );

      // Enregistrement auprès du gestionnaire central
      ref.read(videoPlayerManagerProvider).registerPlayer(
        id: _playerId,
        controller: controller,
        onPauseRequested: () {
          if (mounted) setState(() {});
        },
      );

      setState(() {
        _videoPlayerController = controller;
        _chewieController = chewie;
        _isLoading = false;
      });

      // Démarrage via le gestionnaire central (qui coupe tout autre flux)
      await ref.read(videoPlayerManagerProvider).play(_playerId);

      // 6. Démarrage du heartbeat périodique de progression (toutes les 10 secondes)
      _startProgressTimer();
    } on DioException catch (e) {
      if (_isDisposed) return;
      setState(() {
        _isLoading = false;
        _errorCode = e.response?.statusCode;
      });
    } catch (e) {
      if (_isDisposed) return;
      setState(() {
        _isLoading = false;
        _customError = e.toString();
      });
    }
  }

  void _onVideoControllerUpdate() {
    final controller = _videoPlayerController;
    if (controller == null || !controller.value.isInitialized) return;

    final pos = controller.value.position;
    final dur = controller.value.duration;

    if (dur > Duration.zero) {
      final isFinished = pos >= dur - const Duration(seconds: 1);
      _checkAdGate(pos, dur, completed: isFinished);

      // Détection de fin de vidéo pour auto-play next episode
      if (isFinished) {
        if (_hasNextVideo && !_showingNextPrompt && !_isGateLockedLocally && !_showingAdGatePrompt) {
          _startAutoNextCountdown();
        }
      }
    }
  }

  /// Vérifie si la progression de la vidéo déclenche le verrou de publicité avec récompense
  void _checkAdGate(Duration position, Duration duration, {bool completed = false}) {
    if (_showingAdGatePrompt || _isDisposed) return;
    final user = ref.read(authProvider).user;
    final watchGate = ref.read(watchGateProvider);

    // Si déjà verrouillé et non exempté
    if (watchGate.isGateLocked && !watchGate.isUserExempt(user)) {
      _triggerAdGate();
      return;
    }

    final isLocked = watchGate.recordVideoProgress(
      videoId: _currentVideo.id.toString(),
      position: position,
      duration: duration,
      completed: completed,
      user: user,
    );

    if (isLocked) {
      _triggerAdGate();
    }
  }

  /// Met en pause et affiche la proposition de regarder une publicité récompensée
  void _triggerAdGate() {
    if (_showingAdGatePrompt || !mounted) return;
    _showingAdGatePrompt = true;

    // Coupure immédiate du lecteur et du compte à rebours
    ref.read(videoPlayerManagerProvider).pause(_playerId);
    _videoPlayerController?.pause();
    _autoNextTimer?.cancel();
    setState(() {
      _showingNextPrompt = false;
      _isGateLockedLocally = true;
    });

    final watchGate = ref.read(watchGateProvider);
    final videosCount = watchGate.currentCycleThreshold;

    AdGatePromptSheet.show(
      context,
      videosToUnlock: videosCount,
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

  /// Déclenche l'affichage plein écran de l'annonce AdMob avec récompense
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
            // Reprise de la vidéo
            ref.read(videoPlayerManagerProvider).play(_playerId);
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
                  ref.read(videoPlayerManagerProvider).play(_playerId);
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
                ref.read(videoPlayerManagerProvider).play(_playerId);
              },
            ),
          ),
        );
      }
    }
  }

  /// Démarre le compte à rebours de passage à l'épisode suivant
  void _startAutoNextCountdown() {
    _showingNextPrompt = true;
    _countdownSeconds = 5;
    setState(() {});

    _autoNextTimer?.cancel();
    _autoNextTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_countdownSeconds > 1) {
        setState(() => _countdownSeconds--);
      } else {
        timer.cancel();
        _playNextEpisode();
      }
    });
  }

  void _cancelAutoNext() {
    _autoNextTimer?.cancel();
    setState(() {
      _showingNextPrompt = false;
    });
  }

  Future<void> _playNextEpisode() async {
    if (!_hasNextVideo) return;

    // Vérifier si le quota est bloqué avant d'enchaîner
    final user = ref.read(authProvider).user;
    final watchGate = ref.read(watchGateProvider);
    if (watchGate.isGateLocked && !watchGate.isUserExempt(user)) {
      _triggerAdGate();
      return;
    }

    _autoNextTimer?.cancel();
    _releasePlayerSync();
    setState(() {
      _currentIndex++;
      _currentVideo = _playlist[_currentIndex];
    });
    _initPlayer();
  }

  Future<void> _playPreviousEpisode() async {
    if (!_hasPreviousVideo) return;
    _autoNextTimer?.cancel();
    _releasePlayerSync();
    setState(() {
      _currentIndex--;
      _currentVideo = _playlist[_currentIndex];
    });
    _initPlayer();
  }

  /// Démarre l'envoi de la progression toutes les 10 secondes
  void _startProgressTimer() {
    _progressTimer?.cancel();
    _progressTimer = Timer.periodic(const Duration(seconds: 10), (_) {
      _sendCurrentProgress(isCompletedCheck: false);
    });
  }

  /// Synchronise la position de lecture actuelle avec le backend
  void _sendCurrentProgress({bool isCompletedCheck = false}) {
    final controller = _videoPlayerController;
    if (controller == null || !controller.value.isInitialized) return;

    final pos = controller.value.position.inSeconds.toDouble();
    final dur = controller.value.duration.inSeconds.toDouble();
    if (dur <= 0) return;

    final completed = isCompletedCheck && (pos >= dur - 15 || pos / dur > 0.92);

    ref.read(historyProvider.notifier).updateProgress(
          _currentVideo.id,
          pos,
          completed,
        );
  }

  /// Libération synchrone et immédiate des ressources du contrôleur
  /// (Évite tout lecteur fantôme ou son persistant en arrière-plan)
  void _releasePlayerSync() {
    _progressTimer?.cancel();
    _autoNextTimer?.cancel();
    _sendCurrentProgress(isCompletedCheck: true);

    final stopVideoId = _currentVideo.id;
    unawaited(_notifyStopStream(stopVideoId));

    ref.read(videoPlayerManagerProvider).unregisterPlayer('player_$stopVideoId');

    final ctrl = _videoPlayerController;
    final chewie = _chewieController;
    _videoPlayerController = null;
    _chewieController = null;

    if (ctrl != null) {
      ctrl.removeListener(_onVideoControllerUpdate);
      ctrl.pause();
      chewie?.dispose();
      ctrl.dispose();
    }
  }

  /// Notification non-bloquante au serveur de la libération du quota
  Future<void> _notifyStopStream(int videoId) async {
    try {
      await apiClient.dio.post(ApiConstants.videoStop(videoId));
    } catch (_) {
      // Ignorer l'erreur réseau à la fermeture
    }
  }

  @override
  void dispose() {
    _isDisposed = true;
    appRouteObserver.unsubscribe(this);
    WidgetsBinding.instance.removeObserver(this);
    _releasePlayerSync();

    // Rétablir l'orientation automatique et l'UI système
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final user = ref.watch(authProvider).user;
    final watchGate = ref.watch(watchGateProvider);
    final isGateLocked = (watchGate.isGateLocked || _isGateLockedLocally) && !watchGate.isUserExempt(user);

    String? displayError;
    if (_errorCode == 429) {
      displayError = l10n.streamLimitReached;
    } else if (_errorCode == 404) {
      displayError = l10n.videoNotFound;
    } else if (_errorCode != null || _customError != null) {
      displayError = _customError ?? l10n.cannotPlayVideo;
    }

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Stack(
          children: [
            // 1. Contenu principal du lecteur
            Center(
              child: _isLoading
                  ? Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(color: AppTheme.netflixRed),
                        const SizedBox(height: 16),
                        Text(
                          l10n.loadingStream,
                          style: const TextStyle(color: Colors.white70, fontSize: 14),
                        ),
                      ],
                    )
                  : displayError != null
                      ? Padding(
                          padding: const EdgeInsets.all(24.0),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.cloud_off, color: Colors.orangeAccent, size: 56),
                              const SizedBox(height: 16),
                              Text(
                                displayError,
                                textAlign: TextAlign.center,
                                style: const TextStyle(color: Colors.white, fontSize: 15),
                              ),
                              const SizedBox(height: 24),
                              ElevatedButton.icon(
                                onPressed: _initPlayer,
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AppTheme.netflixRed,
                                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                                ),
                                icon: const Icon(Icons.refresh),
                                label: Text(l10n.retry),
                              ),
                            ],
                          ),
                        )
                      : _chewieController != null &&
                              _chewieController!.videoPlayerController.value.isInitialized
                          ? Chewie(controller: _chewieController!)
                          : const SizedBox.shrink(),
            ),

            // 2. Bouton retour flottant
            Positioned(
              top: 12,
              left: 12,
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.6),
                  shape: BoxShape.circle,
                ),
                child: IconButton(
                  icon: const Icon(Icons.arrow_back, color: Colors.white),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ),
            ),

            // 3. Titre de la vidéo en haut au centre
            Positioned(
              top: 18,
              left: 70,
              right: 70,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.6),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.white10),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (_currentVideo.episodeNumber != null) ...[
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppTheme.netflixRed,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          'EP ${_currentVideo.episodeNumber}',
                          style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                        ),
                      ),
                      const SizedBox(width: 8),
                    ],
                    Flexible(
                      child: Text(
                        _currentVideo.episodeTitle ?? _currentVideo.title,
                        textAlign: TextAlign.center,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // 4. Bouton Favori en haut à droite
            Positioned(
              top: 12,
              right: 12,
              child: Consumer(
                builder: (context, ref, _) {
                  final favorites = ref.watch(favoritesProvider).value ?? [];
                  final isFav = favorites.any((v) => v.id == _currentVideo.id);

                  return Container(
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.6),
                      shape: BoxShape.circle,
                    ),
                    child: IconButton(
                      icon: Icon(
                        isFav ? Icons.favorite : Icons.favorite_border,
                        color: isFav ? AppTheme.netflixRed : Colors.white,
                      ),
                      onPressed: () {
                        ref.read(favoritesProvider.notifier).toggleFavorite(_currentVideo);
                      },
                    ),
                  );
                },
              ),
            ),

            // 5a. Bouton épisode précédent (si disponible dans la playlist)
            if (_hasPreviousVideo && !_showingNextPrompt)
              Positioned(
                bottom: 24,
                left: 20,
                child: FloatingActionButton.extended(
                  heroTag: 'prev_ep_fab',
                  onPressed: _playPreviousEpisode,
                  backgroundColor: Colors.black.withValues(alpha: 0.6),
                  icon: const Icon(Icons.skip_previous, color: Colors.white),
                  label: const Text(
                    'Précédent',
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                ),
              ),

            // 5b. Bouton épisode suivant rapide (si disponible dans la playlist)
            if (_hasNextVideo && !_showingNextPrompt)
              Positioned(
                bottom: 24,
                right: 20,
                child: FloatingActionButton.extended(
                  heroTag: 'next_ep_fab',
                  onPressed: _playNextEpisode,
                  backgroundColor: AppTheme.netflixRed.withValues(alpha: 0.85),
                  icon: const Icon(Icons.skip_next, color: Colors.white),
                  label: const Text(
                    'Suivant',
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                ),
              ),

            // 6. Overlay Compte à rebours Auto-Play Next Episode (Style Netflix)
            if (_showingNextPrompt && _nextVideo != null)
              Positioned(
                bottom: 30,
                left: 20,
                right: 20,
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xEE1E1E1E),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.netflixRed.withValues(alpha: 0.6)),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.8),
                        blurRadius: 16,
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      Stack(
                        alignment: Alignment.center,
                        children: [
                          CircularProgressIndicator(
                            value: _countdownSeconds / 5.0,
                            color: AppTheme.netflixRed,
                            backgroundColor: Colors.white12,
                          ),
                          Text(
                            '$_countdownSeconds',
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                          ),
                        ],
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Text(
                              'Prochain épisode dans quelques secondes...',
                              style: TextStyle(color: Colors.white70, fontSize: 11),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              _nextVideo!.episodeTitle ?? _nextVideo!.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                            ),
                          ],
                        ),
                      ),
                      TextButton(
                        onPressed: _cancelAutoNext,
                        child: const Text('Annuler', style: TextStyle(color: Colors.white54)),
                      ),
                      const SizedBox(width: 6),
                      ElevatedButton.icon(
                        onPressed: _playNextEpisode,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.netflixRed,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        ),
                        icon: const Icon(Icons.play_arrow, size: 18),
                        label: const Text('Lire', style: TextStyle(fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                ),
              ),

            // 7. Overlay de verrouillage AdGate (si quota atteint et utilisateur non exempté)
            if (isGateLocked && !_showingAdGatePrompt)
              Positioned.fill(
                child: AdGateLockedOverlay(
                  onWatchAd: _launchRewardedAd,
                  onBack: () => Navigator.of(context).pop(),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
