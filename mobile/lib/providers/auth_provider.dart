import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api/api_client.dart';
import '../core/constants/api_constants.dart';
import '../core/storage/storage_service.dart';
import '../models/user_model.dart';

/// État de la session utilisateur.
class AuthState {
  final bool isAuthenticated;
  final bool isLoading;
  final UserModel? user;
  final String? errorMessage;

  const AuthState({
    this.isAuthenticated = false,
    this.isLoading = true,
    this.user,
    this.errorMessage,
  });

  AuthState copyWith({
    bool? isAuthenticated,
    bool? isLoading,
    UserModel? user,
    String? errorMessage,
  }) {
    return AuthState(
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      isLoading: isLoading ?? this.isLoading,
      user: user ?? this.user,
      errorMessage: errorMessage,
    );
  }
}

/// Gestionnaire d'état d'authentification Riverpod.
class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState()) {
    checkInitialAuth();
  }

  /// Vérifie si un token valide existe au démarrage de l'app
  Future<void> checkInitialAuth() async {
    state = state.copyWith(isLoading: true);
    final token = await storageService.getAccessToken();

    if (token == null) {
      state = state.copyWith(isAuthenticated: false, isLoading: false);
      return;
    }

    try {
      final res = await apiClient.dio.get(ApiConstants.me);
      if (res.statusCode == 200) {
        final user = UserModel.fromJson(res.data);
        state = state.copyWith(
          isAuthenticated: true,
          isLoading: false,
          user: user,
        );
        return;
      }
    } catch (_) {
      // Le token est expiré ou invalide
    }

    await storageService.clearAuthData();
    state = state.copyWith(isAuthenticated: false, isLoading: false);
  }

  /// Connexion classique par nom d'utilisateur et mot de passe
  Future<bool> login(String username, String password) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final res = await apiClient.dio.post(
        ApiConstants.login,
        data: {'username': username.trim(), 'password': password},
      );

      if (res.statusCode == 200) {
        final data = res.data;
        await storageService.setAccessToken(data['access_token']);
        await storageService.setRefreshToken(data['refresh_token']);

        // Récupérer le profil
        final userRes = await apiClient.dio.get(ApiConstants.me);
        final user = UserModel.fromJson(userRes.data);

        state = state.copyWith(
          isAuthenticated: true,
          isLoading: false,
          user: user,
          errorMessage: null,
        );
        return true;
      }
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Erreur lors de la connexion';
      state = state.copyWith(isLoading: false, errorMessage: msg.toString());
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: 'Erreur réseau inattendue');
    }
    return false;
  }

  /// Inscription par code d'invitation obligatoire
  Future<bool> register(String username, String password, String inviteCode) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final res = await apiClient.dio.post(
        ApiConstants.register,
        data: {
          'username': username.trim(),
          'password': password,
          'invite_code': inviteCode.trim(),
        },
      );

      if (res.statusCode == 201) {
        final data = res.data;
        await storageService.setAccessToken(data['access_token']);
        await storageService.setRefreshToken(data['refresh_token']);

        final userRes = await apiClient.dio.get(ApiConstants.me);
        final user = UserModel.fromJson(userRes.data);

        state = state.copyWith(
          isAuthenticated: true,
          isLoading: false,
          user: user,
          errorMessage: null,
        );
        return true;
      }
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? "Échec de l'inscription";
      state = state.copyWith(isLoading: false, errorMessage: msg.toString());
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: 'Erreur réseau inattendue');
    }
    return false;
  }

  /// Déconnexion
  Future<void> logout() async {
    await storageService.clearAuthData();
    state = const AuthState(isAuthenticated: false, isLoading: false);
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier();
});
