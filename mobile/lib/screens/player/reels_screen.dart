import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';

import '../../core/api/api_client.dart';
import '../../core/constants/api_constants.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/services/video_player_manager.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../models/video_model.dart';
import '../../providers/library_provider.dart';
import '../../providers/video_provider.dart';

/// Écran de défilement vertical façon TikTok / Reels avec lecture plein écran instantanée.
class ReelsScreen extends ConsumerStatefulWidget {
  final bool isActive;

  const ReelsScreen({
    super.key,
    this.isActive = true,
  });

  @override
  ConsumerState<ReelsScreen> createState() => _ReelsScreenState();
}

class _ReelsScreenState extends ConsumerState<ReelsScreen> with WidgetsBindingObserver {
  late PageController _pageController;
  int _focusedIndex = 0;
  bool _isAppActive = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _pageController = PageController();
  }

  @override
  void didUpdateWidget(covariant ReelsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.isActive && oldWidget.isActive) {
      // Coupure immédiate si l'onglet Reels n'est plus actif
      ref.read(videoPlayerManagerProvider).pauseAll();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      _isAppActive = false;
      ref.read(videoPlayerManagerProvider).pauseAll();
    } else if (state == AppLifecycleState.resumed) {
      _isAppActive = true;
    }
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    ref.read(videoPlayerManagerProvider).pauseAll();
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final videoListAsync = ref.watch(videoListProvider);
    final l10n = context.l10n;

    return Scaffold(
      backgroundColor: Colors.black,
      body: videoListAsync.when(
        loading: () => const Center(
          child: CircularProgressIndicator(color: AppTheme.netflixRed),
        ),
        error: (err, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.wifi_off, color: Colors.redAccent, size: 48),
              const SizedBox(height: 12),
              Text('Erreur : $err', style: const TextStyle(color: Colors.white70)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => ref.invalidate(videoListProvider),
                child: Text(l10n.retry),
              ),
            ],
          ),
        ),
        data: (videos) {
          if (videos.isEmpty) {
            return const Center(
              child: Text(
                'Aucune vidéo disponible pour le zapping',
                style: TextStyle(color: Colors.white60),
              ),
            );
          }

          return PageView.builder(
            controller: _pageController,
            scrollDirection: Axis.vertical,
            itemCount: videos.length,
            onPageChanged: (index) {
              setState(() {
                _focusedIndex = index;
              });
            },
            itemBuilder: (context, index) {
              final isCurrent = widget.isActive && _isAppActive && (index == _focusedIndex);
              return ReelPlayerItem(
                key: ValueKey('reel_item_${videos[index].id}'),
                video: videos[index],
                isActive: isCurrent,
              );
            },
          );
        },
      ),
    );
  }
}

/// Élément de lecteur vidéo individuel pour chaque carte du Reel
class ReelPlayerItem extends ConsumerStatefulWidget {
  final VideoModel video;
  final bool isActive;

  const ReelPlayerItem({
    super.key,
    required this.video,
    required this.isActive,
  });

  @override
  ConsumerState<ReelPlayerItem> createState() => _ReelPlayerItemState();
}

class _ReelPlayerItemState extends ConsumerState<ReelPlayerItem> {
  VideoPlayerController? _controller;
  bool _isInitialized = false;
  bool _isPlaying = false;
  bool _isMuted = false;
  bool _showHeartAnimation = false;

  String get _playerId => 'reel_${widget.video.id}';

  @override
  void initState() {
    super.initState();
    if (widget.isActive) {
      _initVideo();
    }
  }

  @override
  void didUpdateWidget(covariant ReelPlayerItem oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isActive && !oldWidget.isActive) {
      if (_controller == null) {
        _initVideo();
      } else {
        ref.read(videoPlayerManagerProvider).play(_playerId);
        if (mounted) setState(() => _isPlaying = true);
      }
    } else if (!widget.isActive && oldWidget.isActive) {
      ref.read(videoPlayerManagerProvider).pause(_playerId);
      if (mounted) setState(() => _isPlaying = false);
    }
  }

  Future<void> _initVideo() async {
    try {
      final baseUrl = await storageService.getServerUrl();
      final accessToken = await storageService.getAccessToken();

      String? streamToken;
      try {
        final tokenRes = await apiClient.dio.post(
          ApiConstants.videoStreamToken(widget.video.id),
        );
        streamToken = tokenRes.data['stream_token'];
      } catch (_) {
        streamToken = accessToken;
      }

      final streamUri = Uri.parse(
        '$baseUrl${ApiConstants.videoStream(widget.video.id)}?token=$streamToken',
      );

      final ctrl = VideoPlayerController.networkUrl(
        streamUri,
        httpHeaders: {
          if (accessToken != null) 'Authorization': 'Bearer $accessToken',
        },
      );

      await ctrl.initialize();
      ctrl.setLooping(true);

      if (!mounted) {
        ctrl.dispose();
        return;
      }

      // Enregistrement dans le gestionnaire central
      ref.read(videoPlayerManagerProvider).registerPlayer(
        id: _playerId,
        controller: ctrl,
        onPauseRequested: () {
          if (mounted) setState(() => _isPlaying = false);
        },
      );

      setState(() {
        _controller = ctrl;
        _isInitialized = true;
      });

      if (widget.isActive) {
        await ref.read(videoPlayerManagerProvider).play(_playerId);
        if (mounted) setState(() => _isPlaying = true);
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    ref.read(videoPlayerManagerProvider).unregisterPlayer(_playerId);
    final ctrl = _controller;
    _controller = null;
    ctrl?.pause();
    ctrl?.dispose();
    super.dispose();
  }

  void _togglePlayPause() {
    if (_controller == null || !_isInitialized) return;
    if (_controller!.value.isPlaying) {
      ref.read(videoPlayerManagerProvider).pause(_playerId);
      setState(() => _isPlaying = false);
    } else {
      ref.read(videoPlayerManagerProvider).play(_playerId);
      setState(() => _isPlaying = true);
    }
  }

  void _toggleMute() {
    if (_controller == null || !_isInitialized) return;
    setState(() {
      _isMuted = !_isMuted;
      _controller!.setVolume(_isMuted ? 0.0 : 1.0);
    });
  }

  void _onDoubleTap() {
    setState(() => _showHeartAnimation = true);
    ref.read(favoritesProvider.notifier).toggleFavorite(widget.video);
    Future.delayed(const Duration(milliseconds: 700), () {
      if (mounted) setState(() => _showHeartAnimation = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: _togglePlayPause,
      onDoubleTap: _onDoubleTap,
      child: Stack(
        fit: StackFit.expand,
        children: [
          // 1. Vidéo en arrière-plan
          _controller != null && _isInitialized
              ? FittedBox(
                  fit: BoxFit.cover,
                  child: SizedBox(
                    width: _controller!.value.size.width,
                    height: _controller!.value.size.height,
                    child: VideoPlayer(_controller!),
                  ),
                )
              : Container(
                  color: Colors.black,
                  child: const Center(
                    child: CircularProgressIndicator(color: AppTheme.netflixRed),
                  ),
                ),

          // 2. Dégradé sombre bas et haut
          Positioned.fill(
            child: Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Color(0x88000000),
                    Colors.transparent,
                    Colors.transparent,
                    Color(0xCC000000),
                  ],
                  stops: [0.0, 0.25, 0.7, 1.0],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
            ),
          ),

          // 3. Indicateur Play/Pause au centre lors de la pause
          if (!_isPlaying && _isInitialized)
            const Center(
              child: Icon(
                Icons.play_circle_fill,
                size: 72,
                color: Colors.white70,
              ),
            ),

          // 4. Animation Cœur double-tap
          if (_showHeartAnimation)
            const Center(
              child: Icon(
                Icons.favorite,
                size: 110,
                color: AppTheme.netflixRed,
              ),
            ),

          // 5. Actions latérales droites (TikTok style)
          Positioned(
            right: 14,
            bottom: 60,
            child: Column(
              children: [
                // Bouton Favoris (Cœur)
                Consumer(
                  builder: (context, ref, _) {
                    final favorites = ref.watch(favoritesProvider).value ?? [];
                    final isFav = favorites.any((v) => v.id == widget.video.id);

                    return Column(
                      children: [
                        IconButton(
                          iconSize: 34,
                          icon: Icon(
                            isFav ? Icons.favorite : Icons.favorite_border,
                            color: isFav ? AppTheme.netflixRed : Colors.white,
                          ),
                          onPressed: () {
                            ref.read(favoritesProvider.notifier).toggleFavorite(widget.video);
                          },
                        ),
                        Text(
                          isFav ? '1' : '0',
                          style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold),
                        ),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),

                // Bouton Son / Mute
                IconButton(
                  iconSize: 30,
                  icon: Icon(
                    _isMuted ? Icons.volume_off : Icons.volume_up,
                    color: Colors.white,
                  ),
                  onPressed: _toggleMute,
                ),
                const SizedBox(height: 18),

                // Badge Catégorie
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.7),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white24),
                  ),
                  child: Text(
                    widget.video.category,
                    style: const TextStyle(color: Colors.white70, fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),

          // 6. Informations textuelles en bas à gauche
          Positioned(
            left: 16,
            right: 80,
            bottom: 24,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  widget.video.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    shadows: [
                      Shadow(color: Colors.black, blurRadius: 4, offset: Offset(0, 1)),
                    ],
                  ),
                ),
                if (widget.video.caption != null && widget.video.caption!.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    widget.video.caption!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 12,
                      shadows: [
                        Shadow(color: Colors.black, blurRadius: 4, offset: Offset(0, 1)),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),

          // 7. Barre de progression fine au bas de l'écran
          if (_controller != null && _isInitialized)
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: VideoProgressIndicator(
                _controller!,
                allowScrubbing: true,
                colors: const VideoProgressColors(
                  playedColor: AppTheme.netflixRed,
                  bufferedColor: Colors.white24,
                  backgroundColor: Colors.transparent,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
