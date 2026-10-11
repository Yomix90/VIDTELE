import 'package:flutter/material.dart';

/// Effet de chargement affiché tant que la première image de la vidéo n'est pas prête :
/// halo pulsé autour d'un anneau de progression et libellé « Chargement… ».
/// Posé par-dessus l'affiche de l'épisode (déjà affichée en fond par le lecteur).
class ChargementVideo extends StatefulWidget {
  final String libelle;
  final Color couleur;

  const ChargementVideo({
    super.key,
    required this.libelle,
    this.couleur = const Color(0xFFE50914),
  });

  @override
  State<ChargementVideo> createState() => _ChargementVideoState();
}

class _ChargementVideoState extends State<ChargementVideo> with SingleTickerProviderStateMixin {
  late final AnimationController _animation = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..repeat();

  @override
  void dispose() {
    _animation.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Respecte le réglage système « Supprimer les animations »
    final sansAnimation = MediaQuery.of(context).disableAnimations;
    return Semantics(
      liveRegion: true,
      label: widget.libelle,
      child: DecoratedBox(
        // Assombrit légèrement l'affiche pour que l'indicateur ressorte
        decoration: const BoxDecoration(color: Color(0x59000000)),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 96,
                height: 96,
                child: AnimatedBuilder(
                  animation: _animation,
                  builder: (context, _) {
                    final t = sansAnimation ? 0.0 : _animation.value;
                    return Stack(
                      alignment: Alignment.center,
                      children: [
                        // Halo qui s'élargit et s'estompe
                        Opacity(
                          opacity: (1 - t) * 0.55,
                          child: Container(
                            width: 56 + 40 * t,
                            height: 56 + 40 * t,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(color: widget.couleur, width: 2),
                            ),
                          ),
                        ),
                        // Disque central
                        Container(
                          width: 56,
                          height: 56,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: Colors.black.withValues(alpha: 0.65),
                            boxShadow: [
                              BoxShadow(color: widget.couleur.withValues(alpha: 0.35), blurRadius: 18),
                            ],
                          ),
                          child: const Icon(Icons.play_arrow_rounded, color: Colors.white, size: 30),
                        ),
                        SizedBox(
                          width: 64,
                          height: 64,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            color: widget.couleur,
                            backgroundColor: Colors.white12,
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
              const SizedBox(height: 14),
              Text(
                widget.libelle,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.4,
                  shadows: [Shadow(color: Colors.black, blurRadius: 6)],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
