import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/localization/app_localizations.dart';
import '../../core/storage/storage_service.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/locale_provider.dart';
import '../admin/admin_screen.dart';
import '../auth/login_screen.dart';
import '../debug/ads_debug_screen.dart';
import '../library/history_screen.dart';
import '../../core/services/update_service.dart';
import 'package:flutter/foundation.dart';

/// Écran des Paramètres et Profil avec support trilingue FR / EN / AR (RTL)
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final user = authState.user;
    final currentLocale = ref.watch(localeProvider);
    final l10n = context.l10n;

    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      appBar: AppBar(
        title: Text(l10n.navProfile),
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
                        user?.username ?? l10n.defaultUsername,
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
                                  ? l10n.roleAdminBadge
                                  : l10n.roleVipBadge,
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
            l10n.preferencesHeader,
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 13,
              fontWeight: FontWeight.bold,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 10),

          // Historique de visionnage
          ListTile(
            tileColor: AppTheme.netflixCard,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            leading: const Icon(Icons.history_rounded, color: Colors.white),
            title: Text(
              l10n.navHistory,
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
            ),
            subtitle: const Text(
              'Reprenez vos lectures et épisodes en cours',
              style: TextStyle(color: Colors.white54, fontSize: 12),
            ),
            trailing: const Icon(Icons.chevron_right, color: Colors.white38),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const HistoryScreen()),
              );
            },
          ),
          const SizedBox(height: 10),

          // Sélecteur de langue trilingue (Français 🇫🇷 / English 🇬🇧 / العربية 🇲🇦)
          ListTile(
            tileColor: AppTheme.netflixCard,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            leading: const Icon(Icons.language, color: Colors.white),
            title: Text(
              l10n.displayLanguage,
              style: const TextStyle(color: Colors.white),
            ),
            subtitle: Text(
              l10n.currentLangName,
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
                DropdownMenuItem(value: 'en', child: Text('English 🇬🇧')),
                DropdownMenuItem(value: 'ar', child: Text('العربية 🇲🇦 (RTL)')),
              ],
              onChanged: (newLang) {
                if (newLang != null) {
                  ref.read(localeProvider.notifier).setLocale(newLang);
                }
              },
            ),
          ),
          const SizedBox(height: 10),

          // Configuration URL Serveur
          ListTile(
            tileColor: AppTheme.netflixCard,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            leading: const Icon(Icons.dns_outlined, color: Colors.white),
            title: Text(
              l10n.serverAddressOption,
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
            onTap: () => _editServerUrl(context, l10n),
          ),
          const SizedBox(height: 24),

          // Section Administration & Développeur (visible si admin ou en debug)
          if (user?.isAdmin == true || kDebugMode) ...[
            Text(
              user?.isAdmin == true ? l10n.adminPanelHeader : 'Outils Développeur',
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 13,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: 10),
            if (user?.isAdmin == true) ...[
              ListTile(
                tileColor: AppTheme.netflixCard,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                leading: const Icon(Icons.admin_panel_settings, color: Colors.amber),
                title: Text(
                  l10n.adminServerAndSync,
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                ),
                subtitle: Text(
                  l10n.adminServerAndSyncDesc,
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
              const SizedBox(height: 10),
            ],
            ListTile(
              tileColor: AppTheme.netflixCard,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              leading: const Icon(Icons.monetization_on_outlined, color: Colors.greenAccent),
              title: const Text(
                'Diagnostic Publicités AdMob',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
              subtitle: const Text(
                'Tester les annonces vidéo avec récompense et l\'état UMP',
                style: TextStyle(color: Colors.white60, fontSize: 12),
              ),
              trailing: const Icon(Icons.chevron_right, color: Colors.white38),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const AdsDebugScreen()),
                );
              },
            ),
            const SizedBox(height: 24),
          ],

          // Informations Version & Vérification de mise à jour OTA
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.04),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.white10),
            ),
            child: Column(
              children: [
                Text(
                  l10n.appVersionInfo,
                  style: const TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                Text(
                  l10n.engineInfo,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white38, fontSize: 11),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: () => UpdateService.checkForUpdates(context, silentOnNoUpdate: false),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white70,
                    side: const BorderSide(color: Colors.white24),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: const Icon(Icons.refresh, size: 16, color: AppTheme.netflixRed),
                  label: Text(
                    l10n.checkUpdateTitle,
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Bouton Déconnexion
          ElevatedButton.icon(
            onPressed: () => _confirmLogout(context, ref, l10n),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF2E2E2E),
              foregroundColor: Colors.redAccent,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            icon: const Icon(Icons.logout, size: 20),
            label: Text(
              l10n.logOutButton,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  void _editServerUrl(BuildContext context, AppLocalizations l10n) async {
    final currentUrl = await storageService.getServerUrl();
    final controller = TextEditingController(text: currentUrl);

    if (!context.mounted) return;

    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.netflixCard,
        title: Text(l10n.editServerAddressTitle, style: const TextStyle(color: Colors.white)),
        content: TextField(
          controller: controller,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            hintText: 'https://vidtele.digitlab.dev',
            hintStyle: TextStyle(color: Colors.white38),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(l10n.cancel, style: const TextStyle(color: Colors.white60)),
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
            child: Text(l10n.save),
          ),
        ],
      ),
    );
  }

  void _confirmLogout(BuildContext context, WidgetRef ref, AppLocalizations l10n) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.netflixCard,
        title: Text(
          l10n.confirmLogoutTitle,
          style: const TextStyle(color: Colors.white),
        ),
        content: Text(
          l10n.confirmLogoutMessage,
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(
              l10n.cancel,
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
            child: Text(l10n.logOutButton),
          ),
        ],
      ),
    );
  }
}
