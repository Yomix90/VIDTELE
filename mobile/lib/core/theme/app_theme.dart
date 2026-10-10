import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Système de design et thèmes pour Atlas Play / VidTele.
/// Conçu pour une expérience de streaming cinéma haut de gamme :
/// fond sombre ultra-profond (OLED friendly), contrastes soignés,
/// typographies adaptées (Poppins en latin, Cairo en arabe)
/// et animations douces.
class AppTheme {
  // Palette de couleurs signature
  static const Color netflixBlack = Color(0xFF09090C);
  static const Color netflixDarkGray = Color(0xFF131318);
  static const Color netflixCard = Color(0xFF1B1B22);
  static const Color netflixCardElevated = Color(0xFF24242E);
  static const Color netflixRed = Color(0xFFE50914);
  static const Color netflixRedGlow = Color(0xFFFF2442);
  static const Color netflixLightGray = Color(0xFF8E8E9B);
  static const Color netflixWhite = Color(0xFFF8F8FC);
  static const Color netflixGold = Color(0xFFFFB800);
  static const Color netflixBorder = Color(0x1AFFFFFF);

  /// Génère le thème sombre avec typographie adaptée à la langue (RTL / LTR)
  static ThemeData getDarkTheme([Locale? locale]) {
    final isArabic = locale?.languageCode == 'ar';
    final activeFontFamily = isArabic ? GoogleFonts.cairo().fontFamily : GoogleFonts.poppins().fontFamily;

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      fontFamily: activeFontFamily,
      scaffoldBackgroundColor: netflixBlack,
      primaryColor: netflixRed,
      colorScheme: const ColorScheme.dark(
        primary: netflixRed,
        secondary: Color(0xFF38BDF8),
        surface: netflixDarkGray,
        error: Color(0xFFEF4444),
        onPrimary: Colors.white,
        onSurface: netflixWhite,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        scrolledUnderElevation: 0,
        titleTextStyle: TextStyle(
          color: netflixWhite,
          fontSize: 20,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.5,
        ),
        iconTheme: IconThemeData(color: Colors.white),
      ),
      cardTheme: CardThemeData(
        color: netflixCard,
        elevation: 4,
        shadowColor: Colors.black.withValues(alpha: 0.5),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: netflixBorder, width: 0.8),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Color(0xFF0F0F14),
        selectedItemColor: netflixRed,
        unselectedItemColor: Color(0xFF888899),
        type: BottomNavigationBarType.fixed,
        elevation: 12,
        selectedLabelStyle: TextStyle(fontWeight: FontWeight.w700, fontSize: 11),
        unselectedLabelStyle: TextStyle(fontWeight: FontWeight.w500, fontSize: 11),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFF16161E),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: netflixBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: netflixBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: netflixRed, width: 1.5),
        ),
        hintStyle: const TextStyle(color: netflixLightGray, fontSize: 13.5),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: netflixRed,
          foregroundColor: Colors.white,
          elevation: 3,
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 13),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.bold,
            letterSpacing: 0.4,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: Colors.white,
          side: const BorderSide(color: Colors.white24, width: 1.2),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 13),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: netflixCardElevated,
        contentTextStyle: const TextStyle(color: Colors.white),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: const BorderSide(color: netflixBorder),
        ),
      ),
    );
  }

  /// Thème clair optionnel
  static ThemeData getLightTheme([Locale? locale]) {
    final isArabic = locale?.languageCode == 'ar';
    final activeFontFamily = isArabic ? GoogleFonts.cairo().fontFamily : GoogleFonts.poppins().fontFamily;

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: activeFontFamily,
      scaffoldBackgroundColor: const Color(0xFFF8F9FA),
      primaryColor: netflixRed,
      colorScheme: const ColorScheme.light(
        primary: netflixRed,
        secondary: Color(0xFF0284C7),
        surface: Colors.white,
        error: Color(0xFFDC2626),
        onPrimary: Colors.white,
        onSurface: Color(0xFF1E293B),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Colors.white,
        selectedItemColor: netflixRed,
        unselectedItemColor: Color(0xFF64748B),
        type: BottomNavigationBarType.fixed,
        elevation: 8,
      ),
    );
  }

  /// Accesseur statique historique pour rétrocompatibilité
  static ThemeData get darkTheme => getDarkTheme();
}
