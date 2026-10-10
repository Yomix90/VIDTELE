import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api/api_client.dart';
import '../constants/api_constants.dart';
import '../localization/app_localizations.dart';
import '../storage/storage_service.dart';
import '../theme/app_theme.dart';

/// Service gérant la détection et l'affichage des mises à jour de l'application Atlas Play.
class UpdateService {
  static const String currentAppVersion = '1.1.0';

  /// Vérifie la version auprès du backend et affiche une boîte de dialogue si nécessaire.
  static Future<void> checkForUpdates(BuildContext context, {bool silentOnNoUpdate = true}) async {
    try {
      final dio = ApiClient().dio;
      final response = await dio.get(
        ApiConstants.appVersion,
        queryParameters: {'current_version': currentAppVersion},
      );

      if (response.statusCode == 200 && response.data != null) {
        final data = response.data as Map<String, dynamic>;
        final bool hasUpdate = data['has_update'] == true;
        final bool forceUpdate = data['force_update'] == true;
        final String latestVersion = data['latest_version'] ?? currentAppVersion;
        final String title = data['title'] ?? 'Mise à jour Atlas Play';
        final String? downloadUrl = data['download_url'];
        final String? notes = data['release_notes'];

        if (hasUpdate && context.mounted) {
          _showUpdateDialog(
            context,
            title: title,
            latestVersion: latestVersion,
            downloadUrl: downloadUrl,
            notes: notes,
            forceUpdate: forceUpdate,
          );
        } else if (!silentOnNoUpdate && context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Votre application Atlas Play est à jour ! (v$currentAppVersion)'),
              backgroundColor: Colors.green,
            ),
          );
        }
      }
    } catch (e) {
      // Ignorer silencieusement si le serveur n'est pas encore joignable
    }
  }

  static void _showUpdateDialog(
    BuildContext context, {
    required String title,
    required String latestVersion,
    required String? downloadUrl,
    required String? notes,
    required bool forceUpdate,
  }) {
    final l10n = context.l10n;

    showDialog(
      context: context,
      barrierDismissible: !forceUpdate,
      builder: (ctx) => PopScope(
        canPop: !forceUpdate,
        child: AlertDialog(
          backgroundColor: AppTheme.netflixDarkGray,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Row(
            children: [
              const Icon(Icons.cloud_download, color: AppTheme.netflixRed, size: 28),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.netflixRed.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AppTheme.netflixRed.withValues(alpha: 0.4)),
                ),
                child: Text(
                  'Version: v$currentAppVersion  ➔  v$latestVersion',
                  style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(height: 14),
              if (notes != null && notes.isNotEmpty) ...[
                const Text(
                  'Nouveautés :',
                  style: TextStyle(color: Colors.white70, fontSize: 13, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 6),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.4),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.white10),
                  ),
                  child: Text(
                    notes,
                    style: const TextStyle(color: Colors.white60, fontSize: 12, height: 1.4),
                  ),
                ),
                const SizedBox(height: 14),
              ],
              if (forceUpdate)
                const Text(
                  'Cette mise à jour est indispensable pour continuer à utiliser Atlas Play.',
                  style: TextStyle(color: Colors.amberAccent, fontSize: 12),
                ),
            ],
          ),
          actions: [
            if (!forceUpdate)
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: Text(l10n.laterButton, style: const TextStyle(color: Colors.white54)),
              ),
            ElevatedButton(
              onPressed: () async {
                if (downloadUrl != null && downloadUrl.isNotEmpty) {
                  String fullUrl = downloadUrl;
                  if (!fullUrl.startsWith('http://') && !fullUrl.startsWith('https://')) {
                    final baseUrl = await storageService.getServerUrl();
                    fullUrl = '$baseUrl${fullUrl.startsWith('/') ? '' : '/'}$fullUrl';
                  }
                  final uri = Uri.tryParse(fullUrl);
                  if (uri != null && await canLaunchUrl(uri)) {
                    await launchUrl(uri, mode: LaunchMode.externalApplication);
                  }
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.netflixRed,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              child: Text(l10n.updateNowButton, style: const TextStyle(fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      ),
    );
  }
}
