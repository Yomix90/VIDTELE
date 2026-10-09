import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';
import 'package:chewie/chewie.dart';
import 'package:dio/dio.dart';

import '../../core/api/api_client.dart';
import '../../core/constants/api_constants.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../models/video_model.dart';
import '../../providers/library_provider.dart';

/// Lecteur vidéo immersif Netflix-style avec streaming HTTP 206 partiel,
/// reprise automatique de lecture, et synchronisation de la progression.
class VideoPlayerScreen extends ConsumerStatefulWidget {
  final VideoModel video;

  const VideoPlayerScreen({
    super.key,
    required this.video,
  });

  @override
  ConsumerState<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends ConsumerState<VideoPlayerScreen> {
  VideoPlayerController? _videoPlayerController;
  ChewieController? _chewieController;

  bool _isLoading = true;
  String? _errorMessage;
  Timer? _progressTimer;
  bool _isDisposed = false;

  @override
  void initState() {
    super.initState();
    _initPlayer();
  }

  /// Initialisation du contrôleur vidéo et du streaming sécurisé
  Future<void> _initPlayer() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final baseUrl = await storageService.getServerUrl();
      final accessToken = await storageService.getAccessToken();

      // 1. Obtention d'un jeton de streaming dédié ou utilisation de l'access token
      String? streamToken;
      try {
        final tokenRes = await apiClient.dio.post(
          ApiConstants.videoStreamToken(widget.video.id),
        );
        streamToken = tokenRes.data['stream_token'];
      } catch (e) {
        // En cas de secours, utiliser le jeton d'authentification principal
        streamToken = accessToken;
      }

      if (streamToken == null) {
        throw Exception("Impossible d'obtenir un jeton d'autorisation de streaming.");
      }

      // 2. Construction de l'URL de streaming avec jeton
      final streamUri = Uri.parse(
        '$baseUrl${ApiConstants.videoStream(widget.video.id)}?token=$streamToken',
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

      // 4. Reprise automatique à la dernière position connue (si non terminée)
      if (widget.video.watchProgressSeconds > 0 && !widget.video.isCompleted) {
        final resumePosition = Duration(seconds: widget.video.watchProgressSeconds.toInt());
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
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.error_outline, color: Colors.redAccent, size: 54),
                  const SizedBox(height: 16),
                  Text(
                    'Erreur de lecture : $errorMessage',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 16),
                  ),
                  const SizedBox(height: 20),
                  ElevatedButton(
                    onPressed: _initPlayer,
                    style: ElevatedButton.styleFrom(backgroundColor: AppTheme.netflixRed),
                    child: const Text('Réessayer'),
                  ),
                ],
              ),
            ),
          );
        },
      );

      setState(() {
        _videoPlayerController = controller;
        _chewieController = chewie;
        _isLoading = false;
      });

      // 6. Démarrage du heartbeat périodique de progression (toutes les 10 secondes)
      _startProgressTimer();
    } on DioException catch (e) {
      if (_isDisposed) return;
      String msg = "Erreur de connexion au serveur de streaming.";
      if (e.response?.statusCode == 429) {
        msg = "Limite de flux simultanés atteinte (15 max sur le serveur ou 2 par compte). Veuillez patienter qu'une session se libère.";
      } else if (e.response?.statusCode == 404) {
        msg = "Cette vidéo n'est plus disponible sur le canal Telegram.";
      }
      setState(() {
        _isLoading = false;
        _errorMessage = msg;
      });
    } catch (e) {
      if (_isDisposed) return;
      setState(() {
        _isLoading = false;
        _errorMessage = "Impossible de lancer la vidéo : ${e.toString()}";
      });
    }
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
          widget.video.id,
          pos,
          completed,
        );
  }

  /// Libère la session de stream sur le serveur et nettoie les contrôleurs
  Future<void> _cleanUpAndRelease() async {
    _progressTimer?.cancel();
    _sendCurrentProgress(isCompletedCheck: true);

    try {
      await apiClient.dio.post(ApiConstants.videoStop(widget.video.id));
    } catch (_) {
      // Ignorer l'erreur réseau à la fermeture
    }

    _chewieController?.dispose();
    _videoPlayerController?.dispose();
  }

  @override
  void dispose() {
    _isDisposed = true;
    _cleanUpAndRelease();
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
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Stack(
          children: [
            // Contenu principal du lecteur
            Center(
              child: _isLoading
                  ? const Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        CircularProgressIndicator(color: AppTheme.netflixRed),
                        SizedBox(height: 16),
                        Text(
                          'Chargement du flux vidéo...',
                          style: TextStyle(color: Colors.white70, fontSize: 14),
                        ),
                      ],
                    )
                  : _errorMessage != null
                      ? Padding(
                          padding: const EdgeInsets.all(24.0),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.cloud_off, color: Colors.orangeAccent, size: 56),
                              const SizedBox(height: 16),
                              Text(
                                _errorMessage!,
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
                                label: const Text('Réessayer'),
                              ),
                            ],
                          ),
                        )
                      : _chewieController != null &&
                              _chewieController!.videoPlayerController.value.isInitialized
                          ? Chewie(controller: _chewieController!)
                          : const SizedBox.shrink(),
            ),

            // Bouton retour flottant en haut à gauche
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

            // Titre et métadonnées de la vidéo en haut au centre
            Positioned(
              top: 18,
              left: 70,
              right: 70,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  widget.video.title,
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),

            // Bouton Favori en haut à droite
            Positioned(
              top: 12,
              right: 12,
              child: Consumer(
                builder: (context, ref, _) {
                  final favorites = ref.watch(favoritesProvider).value ?? [];
                  final isFav = favorites.any((v) => v.id == widget.video.id);

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
                        ref.read(favoritesProvider.notifier).toggleFavorite(widget.video);
                      },
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
