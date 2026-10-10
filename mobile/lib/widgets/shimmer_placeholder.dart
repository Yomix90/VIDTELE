import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../core/theme/app_theme.dart';

/// Squelette de chargement cinématique réutilisable (Shimmer)
class ShimmerBox extends StatelessWidget {
  final double? width;
  final double? height;
  final double borderRadius;
  final ShapeBorder? shapeBorder;

  const ShimmerBox({
    super.key,
    this.width,
    this.height,
    this.borderRadius = 8.0,
    this.shapeBorder,
  });

  const ShimmerBox.circular({
    super.key,
    required double size,
  })  : width = size,
        height = size,
        borderRadius = size / 2,
        shapeBorder = const CircleBorder();

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: const Color(0xFF16161E),
      highlightColor: const Color(0xFF262634),
      period: const Duration(milliseconds: 1400),
      child: Container(
        width: width,
        height: height,
        decoration: shapeBorder != null
            ? ShapeDecoration(
                color: const Color(0xFF16161E),
                shape: shapeBorder!,
              )
            : BoxDecoration(
                color: const Color(0xFF16161E),
                borderRadius: BorderRadius.circular(borderRadius),
              ),
      ),
    );
  }
}

/// Squelette pour une rangée horizontale de cartes vidéo / affiches
class ShimmerVideoRow extends StatelessWidget {
  final double cardWidth;
  final double cardHeight;
  final int count;

  const ShimmerVideoRow({
    super.key,
    this.cardWidth = 135,
    this.cardHeight = 195,
    this.count = 4,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: cardHeight,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: count,
        itemBuilder: (context, index) {
          return Padding(
            padding: const EdgeInsets.only(right: 12),
            child: ShimmerBox(
              width: cardWidth,
              height: cardHeight,
              borderRadius: 8,
            ),
          );
        },
      ),
    );
  }
}

/// Squelette pour la bannière Hero d'accueil
class ShimmerHeroBanner extends StatelessWidget {
  const ShimmerHeroBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: const Color(0xFF14141A),
      highlightColor: const Color(0xFF24242F),
      child: Container(
        height: 440,
        width: double.infinity,
        color: AppTheme.netflixDarkGray,
      ),
    );
  }
}
