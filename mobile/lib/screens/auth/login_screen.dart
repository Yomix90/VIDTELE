import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/locale_provider.dart';

/// Écran de connexion et inscription style Netflix avec configurateur d'URL serveur
/// et sélecteur de langue trilingue FR / EN / AR.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  bool _isSignUp = false;
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _inviteCodeController = TextEditingController();
  final _serverUrlController = TextEditingController();

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _inviteCodeController.dispose();
    _serverUrlController.dispose();
    super.dispose();
  }

  void _showServerConfigDialog() async {
    final l10n = context.l10n;
    final currentUrl = await storageService.getServerUrl();
    _serverUrlController.text = currentUrl;

    if (!mounted) return;
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.netflixDarkGray,
        title: Text(l10n.serverUrlDialogTitle),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l10n.serverUrlDialogDesc,
              style: const TextStyle(fontSize: 12, color: Colors.white70),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _serverUrlController,
              decoration: const InputDecoration(
                hintText: 'https://vidtele.digitlab.dev',
                prefixIcon: Icon(Icons.dns, color: AppTheme.netflixRed),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(l10n.cancel, style: const TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            onPressed: () async {
              final newUrl = _serverUrlController.text;
              final messenger = ScaffoldMessenger.of(context);
              final navigator = Navigator.of(context);
              await storageService.setServerUrl(newUrl);
              if (mounted) {
                navigator.pop();
                messenger.showSnackBar(
                  SnackBar(content: Text(l10n.serverUpdated(newUrl))),
                );
              }
            },
            child: Text(l10n.save),
          ),
        ],
      ),
    );
  }

  void _handleSubmit() async {
    final l10n = context.l10n;
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    final inviteCode = _inviteCodeController.text.trim();

    if (username.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(l10n.fillAllFields)),
      );
      return;
    }

    if (_isSignUp) {
      if (inviteCode.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.fillAllFields)),
        );
        return;
      }
      await ref.read(authProvider.notifier).register(username, password, inviteCode);
    } else {
      await ref.read(authProvider.notifier).login(username, password);
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final currentLocale = ref.watch(localeProvider);
    final l10n = context.l10n;

    return Scaffold(
      body: Stack(
        children: [
          // 1. Image d'arrière-plan avec dégradé sombre immersif
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF000000), Color(0xFF141414), Color(0xFF0A0A0A)],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
            ),
          ),

          // 2. Boutons Supérieurs : Sélecteur de Langue & Paramètres Serveur
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // Menu Déroulant Langue Trilingue
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Colors.white24),
                    ),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        value: currentLocale.languageCode,
                        dropdownColor: AppTheme.netflixDarkGray,
                        icon: const Icon(Icons.arrow_drop_down, color: Colors.white70),
                        style: const TextStyle(color: Colors.white, fontSize: 13),
                        items: const [
                          DropdownMenuItem(value: 'fr', child: Text('FR 🇫🇷')),
                          DropdownMenuItem(value: 'en', child: Text('EN 🇬🇧')),
                          DropdownMenuItem(value: 'ar', child: Text('AR 🇲🇦')),
                        ],
                        onChanged: (lang) {
                          if (lang != null) {
                            ref.read(localeProvider.notifier).setLocale(lang);
                          }
                        },
                      ),
                    ),
                  ),

                  // Bouton Paramètres Serveur
                  IconButton(
                    icon: const Icon(Icons.settings, color: Colors.white70),
                    tooltip: l10n.configureBackendServer,
                    onPressed: _showServerConfigDialog,
                  ),
                ],
              ),
            ),
          ),

          // 3. Formulaire de connexion centré
          Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Logo Atlas Play stylisé avec montages et play icon
                  Column(
                    children: [
                      Container(
                        width: 76,
                        height: 76,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFFE50914), Color(0xFF990008)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius: BorderRadius.circular(20),
                          boxShadow: [
                            BoxShadow(
                              color: AppTheme.netflixRed.withValues(alpha: 0.4),
                              blurRadius: 20,
                              offset: const Offset(0, 8),
                            ),
                          ],
                        ),
                        child: const Center(
                          child: Icon(
                            Icons.play_arrow_rounded,
                            size: 52,
                            color: Colors.white,
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),
                      RichText(
                        text: const TextSpan(
                          children: [
                            TextSpan(
                              text: 'ATLAS ',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 28,
                                fontWeight: FontWeight.w900,
                                letterSpacing: 4,
                              ),
                            ),
                            TextSpan(
                              text: 'PLAY',
                              style: TextStyle(
                                color: AppTheme.netflixRed,
                                fontSize: 28,
                                fontWeight: FontWeight.w900,
                                letterSpacing: 4,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    l10n.welcomeSubtitle,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white54, fontSize: 13),
                  ),
                  const SizedBox(height: 36),

                  // Message d'erreur éventuel
                  if (authState.errorMessage != null)
                    Container(
                      padding: const EdgeInsets.all(12),
                      margin: const EdgeInsets.only(bottom: 16),
                      decoration: BoxDecoration(
                        color: Colors.red.withValues(alpha: 0.15),
                        border: Border.all(color: Colors.red.withValues(alpha: 0.5)),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline, color: Colors.redAccent, size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              authState.errorMessage!,
                              style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                            ),
                          ),
                        ],
                      ),
                    ),

                  // Champ Nom d'utilisateur
                  TextField(
                    controller: _usernameController,
                    decoration: InputDecoration(
                      labelText: l10n.username,
                      prefixIcon: const Icon(Icons.person_outline, color: Colors.white54),
                    ),
                  ),
                  const SizedBox(height: 14),

                  // Champ Mot de passe
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    decoration: InputDecoration(
                      labelText: l10n.password,
                      prefixIcon: const Icon(Icons.lock_outline, color: Colors.white54),
                    ),
                  ),
                  const SizedBox(height: 14),

                  // Champ Code d'invitation (uniquement en mode inscription)
                  if (_isSignUp) ...[
                    TextField(
                      controller: _inviteCodeController,
                      decoration: InputDecoration(
                        labelText: l10n.inviteCodeVip,
                        prefixIcon: const Icon(
                          Icons.confirmation_number_outlined,
                          color: Colors.white54,
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                  ],

                  const SizedBox(height: 10),

                  // Bouton d'action principal
                  SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: ElevatedButton(
                      onPressed: authState.isLoading ? null : _handleSubmit,
                      child: authState.isLoading
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                            )
                          : Text(
                              _isSignUp ? l10n.registerButton : l10n.connectButton,
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                            ),
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Bascule Connexion / Inscription
                  TextButton(
                    onPressed: () {
                      setState(() {
                        _isSignUp = !_isSignUp;
                      });
                    },
                    child: Text(
                      _isSignUp ? l10n.alreadyAccountPrompt : l10n.noAccountPrompt,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        decoration: TextDecoration.underline,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
