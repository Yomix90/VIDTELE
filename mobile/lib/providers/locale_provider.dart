import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/constants/api_constants.dart';

/// Notifier pour la gestion dynamique de la langue et du sens de lecture (RTL pour l'arabe)
class LocaleNotifier extends StateNotifier<Locale> {
  LocaleNotifier() : super(const Locale('fr')) {
    _loadSavedLocale();
  }

  Future<void> _loadSavedLocale() async {
    final prefs = await SharedPreferences.getInstance();
    final langCode = prefs.getString(ApiConstants.keyLanguage) ?? 'fr';
    state = Locale(langCode);
  }

  Future<void> setLocale(String langCode) async {
    if (state.languageCode == langCode) return;
    state = Locale(langCode);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(ApiConstants.keyLanguage, langCode);
  }

  bool get isArabic => state.languageCode == 'ar';
}

final localeProvider = StateNotifierProvider<LocaleNotifier, Locale>((ref) {
  return LocaleNotifier();
});
