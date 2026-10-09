import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';

/// Écran de connexion et inscription style Netflix avec configurateur d'URL serveur.
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
    final currentUrl = await storageService.getServerUrl();
    _serverUrlController.text = currentUrl;

    if (!mounted) return;
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.netflixDarkGray,
        title: const Text('Adresse du Serveur VidTele'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Entrez l\'URL de votre serveur (ex: http://192.168.1.100:8000 pour un téléphone physique, ou http://10.0.2.2:8000 pour l\'émulateur Android) :',
              style: TextStyle(fontSize: 12, color: Colors.white70),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _serverUrlController,
              decoration: const InputDecoration(
                hintText: 'http://10.0.2.2:8000',
                prefixIcon: Icon(Icons.dns, color: AppTheme.netflixRed),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Annuler', style: TextStyle(color: Colors.white60)),
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
                  SnackBar(content: Text('Serveur mis à jour : $newUrl')),
                );
              }
            },
            child: const Text('Enregistrer'),
          ),
        ],
      ),
    );
  }

  void _handleSubmit() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    final inviteCode = _inviteCodeController.text.trim();

    if (username.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Veuillez renseigner vos identifiants')),
      );
      return;
    }

    if (_isSignUp) {
      if (inviteCode.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Un code d\'invitation valide est requis')),
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

          // 2. Bouton Paramètres Serveur en haut à droite
          SafeArea(
            child: Align(
              alignment: Alignment.topRight,
              child: IconButton(
                icon: const Icon(Icons.settings, color: Colors.white70),
                tooltip: 'Configurer l\'URL du serveur',
                onPressed: _showServerConfigDialog,
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
                  // Logo VidTele stylisé Netflix
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppTheme.netflixRed,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'V',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 36,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 2,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      const Text(
                        'IDTELE',
                        style: TextStyle(
                          color: AppTheme.netflixRed,
                          fontSize: 32,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 3,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Streaming Vidéo Privé Telegram',
                    style: TextStyle(color: Colors.white54, fontSize: 13),
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
                    decoration: const InputDecoration(
                      labelText: 'Nom d\'utilisateur',
                      prefixIcon: Icon(Icons.person_outline, color: Colors.white54),
                    ),
                  ),
                  const SizedBox(height: 14),

                  // Champ Mot de passe
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    decoration: const InputDecoration(
                      labelText: 'Mot de passe',
                      prefixIcon: Icon(Icons.lock_outline, color: Colors.white54),
                    ),
                  ),
                  const SizedBox(height: 14),

                  // Champ Code d'invitation (uniquement en mode inscription)
                  if (_isSignUp) ...[
                    TextField(
                      controller: _inviteCodeController,
                      decoration: const InputDecoration(
                        labelText: 'Code d\'invitation (Obligatoire)',
                        prefixIcon: Icon(Icons.confirmation_number_outlined, color: Colors.white54),
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
                              _isSignUp ? 'Créer mon compte' : 'S\'identifier',
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
                    child: RichText(
                      text: TextSpan(
                        text: _isSignUp ? 'Déjà membre ? ' : 'Nouveau sur VidTele ? ',
                        style: const TextStyle(color: Colors.white60, fontSize: 14),
                        children: [
                          TextSpan(
                            text: _isSignUp ? 'S\'identifier' : 'S\'inscrire avec un code',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              decoration: TextDecoration.underline,
                            ),
                          ),
                        ],
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
