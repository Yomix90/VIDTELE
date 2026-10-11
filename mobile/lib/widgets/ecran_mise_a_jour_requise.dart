import 'package:flutter/material.dart';

import '../core/localization/app_localizations.dart';
import '../core/services/update_service.dart';
import '../core/theme/app_theme.dart';
import '../core/version/mise_a_jour_requise.dart';
import '../core/version/version_app.dart';

/// Écran plein écran, impossible à fermer, affiché dès qu'une requête reçoit 426.
/// Posé par-dessus toute l'application (MaterialApp.builder).
class EcranMiseAJourRequise extends StatelessWidget {
  final InfoMiseAJourRequise info;

  const EcranMiseAJourRequise({super.key, required this.info});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return PopScope(
      canPop: false,
      child: Material(
        color: AppTheme.netflixBlack,
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.system_update_rounded, size: 72, color: AppTheme.netflixRed),
                  const SizedBox(height: 24),
                  Text(
                    l10n.updateRequiredTitle,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    l10n.updateRequiredMessage,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white70, fontSize: 16, height: 1.4),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'v${VersionApp.actuelle}'
                    '${info.versionMinimale.isNotEmpty ? '  •  ${l10n.minimumVersionLabel(info.versionMinimale)}' : ''}',
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white38, fontSize: 13),
                  ),
                  const SizedBox(height: 32),
                  if (info.urlTelechargement != null)
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: ElevatedButton.icon(
                        onPressed: () => UpdateService.ouvrirLienTelechargement(info.urlTelechargement!),
                        icon: const Icon(Icons.download_rounded),
                        label: Text(l10n.updateNowButton, style: const TextStyle(fontWeight: FontWeight.bold)),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.netflixRed,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
