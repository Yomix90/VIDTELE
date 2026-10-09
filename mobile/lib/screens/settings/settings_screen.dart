import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/locale_provider.dart';
import '../admin/admin_screen.dart';
import '../auth/login_screen.dart';

/// Écran des Paramètres et Profil avec support bilingue FR/AR (RTL)
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final user = authState.user;
    final currentLocale = ref.watch(localeProvider);
    final isArabic = currentLocale.languageCode == 'ar';

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      appBar: AppBar(
        title: Text(isArabic ? 'الإعدادات والملف الشخصي' : 'Paramètres & Profil'),
        backgroundColor: Colors.black.withValues(alpha: 0.8),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Carte Profil Utilisateur
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.netflixCard,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.white10),
            ),
            child: Row(
              children: [
                // Avatar stylisé
                CircleAvatar(
                  radius: 30,
                  backgroundColor: AppTheme.netflixRed,
                  child: Text(
                    (user?.username.isNotEmpty ?? false)
                        ? user!.username[0].toUpperCase()
                        : 'U',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 26,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user?.username ?? 'Utilisateur',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: user?.isAdmin == true
                                  ? Colors.amber.withValues(alpha: 0.2)
                                  : Colors.blueAccent.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(
                                color: user?.isAdmin == true ? Colors.amber : Colors.blueAccent,
                              ),
                            ),
                            child: Text(
                              user?.isAdmin == true
                                  ? (isArabic ? 'مسؤول النظام' : 'ADMINISTRATEUR')
                                  : (isArabic ? 'عضو مميز' : 'MEMBRE VIP'),
                              style: TextStyle(
                                color: user?.isAdmin == true ? Colors.amber : Colors.blueAccent,
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Section Préférences
          Text(
            isArabic ? 'التفضيلات' : 'Préférences Générales',
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 13,
              fontWeight: FontWeight.bold,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 10),

          // Sélecteur de langue (Français / Arabe RTL)
          ListTile(
            tileColor: AppTheme.netflixCard,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            leading: const Icon(Icons.language, color: Colors.white),
            title: Text(
              isArabic ? 'اللغة' : 'Langue d\'affichage',
              style: const TextStyle(color: Colors.white),
            ),
            subtitle: Text(
              isArabic ? 'العربية (من اليمين لليسار)' : 'Français',
              style: const TextStyle(color: Colors.white60, fontSize: 13),
            ),
            trailing: DropdownButton<String>(
              value: currentLocale.languageCode,
              dropdownColor: AppTheme.netflixCard,
              underline: const SizedBox.shrink(),
              icon: const Icon(Icons.arrow_drop_down, color: Colors.white70),
              style: const TextStyle(color: Colors.white),
              items: const [
                DropdownMenuItem(value: 'fr', child: Text('Français 🇫🇷')),
                DropdownMenuItem(value: 'ar', child: Text('العربية 🇲🇦')),
              ],
              onChanged: (newLang) {
                if (newLang != null) {
                  ref.read(localeProvider.notifier).setLocale(newLang);
                }
              },
            ),
          ),
          const SizedBox(height: 12),

          // Configuration URL Serveur
          ListTile(
            tileColor: AppTheme.netflixCard,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            leading: const Icon(Icons.dns_outlined, color: Colors.white),
            title: Text(
              isArabic ? 'عنوان الخادم' : 'Adresse du Serveur Backend',
              style: const TextStyle(color: Colors.white),
            ),
            subtitle: FutureBuilder<String>(
              future: storageService.getServerUrl(),
              builder: (context, snap) => Text(
                snap.data ?? 'http://...',
                style: const TextStyle(color: Colors.white60, fontSize: 12),
              ),
            ),
            trailing: const Icon(Icons.edit, color: Colors.white38, size: 20),
            onTap: () => _editServerUrl(context),
          ),
          const SizedBox(height: 24),

          // Section Administration (visible si admin)
          if (user?.isAdmin == true) ...[
            Text(
              isArabic ? 'إدارة المنصة' : 'Panneau d\'Administration',
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 13,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: 10),
            ListTile(
              tileColor: AppTheme.netflixCard,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              leading: const Icon(Icons.admin_panel_settings, color: Colors.amber),
              title: Text(
                isArabic ? 'لوحة التحكم والعمليات' : 'Gestion du Serveur & Sync',
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
              subtitle: Text(
                isArabic
                    ? 'المزامنة، دعوات التسجيل، وتفريغ الذاكرة'
                    : 'Synchronisation Telegram, invitations VIP, cache',
                style: const TextStyle(color: Colors.white60, fontSize: 12),
              ),
              trailing: const Icon(Icons.chevron_right, color: Colors.white38),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const AdminScreen()),
                );
              },
            ),
            const SizedBox(height: 24),
          ],

          // Informations Version
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.04),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              children: [
                const Text(
                  'VidTele Mobile v1.0.0 (Production)',
                  style: TextStyle(color: Colors.white38, fontSize: 12),
                ),
                const SizedBox(height: 4),
                Text(
                  isArabic
                      ? 'بث مباشر عالي السرعة من تيليغرام'
                      : 'Moteur MTProto Streaming HTTP 206 partiel',
                  style: const TextStyle(color: Colors.white24, fontSize: 11),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Bouton Déconnexion
          ElevatedButton.icon(
            onPressed: () => _confirmLogout(context, ref, isArabic),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF2E2E2E),
              foregroundColor: Colors.redAccent,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            icon: const Icon(Icons.logout, size: 20),
            label: Text(
              isArabic ? 'تسجيل الخروج' : 'Se déconnecter',
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  void _editServerUrl(BuildContext context) async {
    final currentUrl = await storageService.getServerUrl();
    final controller = TextEditingController(text: currentUrl);

    if (!context.mounted) return;

    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.netflixCard,
        title: const Text('Modifier l\'URL du serveur', style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: controller,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            hintText: 'http://192.168.1.X:8000',
            hintStyle: TextStyle(color: Colors.white38),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Annuler', style: TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            onPressed: () async {
              final newUrl = controller.text.trim();
              if (newUrl.isNotEmpty) {
                await storageService.setServerUrl(newUrl);
                if (ctx.mounted) Navigator.pop(ctx);
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.netflixRed),
            child: const Text('Enregistrer'),
          ),
        ],
      ),
    );
  }

  void _confirmLogout(BuildContext context, WidgetRef ref, bool isArabic) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.netflixCard,
        title: Text(
          isArabic ? 'تسجيل الخروج ؟' : 'Confirmer la déconnexion ?',
          style: const TextStyle(color: Colors.white),
        ),
        content: Text(
          isArabic
              ? 'هل أنت متأكد من رغبتك في تسجيل الخروج من هذا الجهاز؟'
              : 'Êtes-vous sûr de vouloir quitter votre session actuelle ?',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(
              isArabic ? 'إلغاء' : 'Annuler',
              style: const TextStyle(color: Colors.white60),
            ),
          ),
          ElevatedButton(
            onPressed: () async {
              final nav = Navigator.of(context);
              Navigator.pop(ctx);
              await ref.read(authProvider.notifier).logout();
              nav.pushAndRemoveUntil(
                MaterialPageRoute(builder: (_) => const LoginScreen()),
                (route) => false,
              );
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.netflixRed),
            child: Text(isArabic ? 'خروج' : 'Déconnexion'),
          ),
        ],
      ),
    );
  }
}
