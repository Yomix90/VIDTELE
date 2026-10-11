import 'package:flutter/material.dart';

import 'touchable_scale.dart';

/// Bouton d'action du lecteur vertical (j'aime, épisodes, son, vitesse, plein écran).
///
/// Conçu pour se détacher nettement de n'importe quelle image : fond sombre opaque à 60 %,
/// liseré clair, ombre portée et libellé sous l'icône. Pas de flou d'arrière-plan : sur une
/// vidéo en mouvement il coûte cher en performance sur les téléphones d'entrée de gamme.
class BoutonActionLecteur extends StatelessWidget {
  final IconData? icone;
  final Widget? contenu; // à la place de l'icône (ex. « 1.5x »)
  final String libelle;
  final String descriptionAccessibilite;
  final VoidCallback onTap;
  final bool actif;
  final Color couleurActive;

  const BoutonActionLecteur({
    super.key,
    this.icone,
    this.contenu,
    required this.libelle,
    required this.descriptionAccessibilite,
    required this.onTap,
    this.actif = false,
    this.couleurActive = const Color(0xFFE50914),
  }) : assert(icone != null || contenu != null);

  static const double diametre = 52;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: descriptionAccessibilite,
      excludeSemantics: true,
      child: TouchableScale(
        onTap: onTap,
        child: SizedBox(
          width: 64, // zone tactile confortable (≥ 48 dp) avec le libellé
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: diametre,
                height: diametre,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: actif ? couleurActive.withValues(alpha: 0.22) : Colors.black.withValues(alpha: 0.6),
                  border: Border.all(
                    color: actif ? couleurActive.withValues(alpha: 0.9) : Colors.white.withValues(alpha: 0.28),
                    width: 1.4,
                  ),
                  boxShadow: const [
                    BoxShadow(color: Color(0x80000000), blurRadius: 12, offset: Offset(0, 3)),
                  ],
                ),
                child: contenu ??
                    Icon(
                      icone,
                      size: 26,
                      color: actif ? couleurActive : Colors.white,
                    ),
              ),
              const SizedBox(height: 5),
              Text(
                libelle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.2,
                  shadows: [
                    Shadow(color: Colors.black, blurRadius: 6),
                    Shadow(color: Colors.black87, blurRadius: 2, offset: Offset(0, 1)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
