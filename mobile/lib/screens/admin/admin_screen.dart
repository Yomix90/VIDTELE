import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api/api_client.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/video_provider.dart';

/// Écran d'administration mobile pour les administrateurs VidTele
class AdminScreen extends ConsumerStatefulWidget {
  const AdminScreen({super.key});

  @override
  ConsumerState<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends ConsumerState<AdminScreen> {
  bool _isLoadingStats = true;
  bool _isSyncing = false;
  bool _isClearingCache = false;

  Map<String, dynamic>? _stats;
  String? _syncMessage;

  @override
  void initState() {
    super.initState();
    _fetchStats();
  }

  Future<void> _fetchStats() async {
    setState(() => _isLoadingStats = true);
    try {
      final res = await apiClient.dio.get('/api/admin/stats');
      setState(() {
        _stats = res.data;
        _isLoadingStats = false;
      });
    } catch (e) {
      setState(() => _isLoadingStats = false);
    }
  }

  Future<void> _triggerSync() async {
    setState(() {
      _isSyncing = true;
      _syncMessage = null;
    });

    try {
      final res = await apiClient.dio.post('/api/admin/sync');
      final data = res.data;
      setState(() {
        _syncMessage =
            "Sync réussie ! +${data['added']} ajoutées, ${data['updated']} mises à jour (${data['total_messages']} messages scannés).";
      });
      // Rafraîchir les vidéos
      ref.invalidate(videoListProvider);
      _fetchStats();
    } catch (e) {
      setState(() {
        _syncMessage = "Erreur de synchronisation : $e";
      });
    } finally {
      setState(() => _isSyncing = false);
    }
  }

  Future<void> _clearCache() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.netflixCard,
        title: const Text('Purger le cache local ?', style: TextStyle(color: Colors.white)),
        content: const Text(
          'Les fichiers vidéo mis en cache seront supprimés du serveur. Ils seront re-téléchargés automatiquement à la prochaine lecture.',
          style: TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Annuler', style: TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.netflixRed),
            child: const Text('Purger'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    setState(() => _isClearingCache = true);
    try {
      await apiClient.dio.post('/api/admin/cache/clear');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Cache purgé avec succès !')),
        );
      }
      _fetchStats();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur : $e')),
        );
      }
    } finally {
      setState(() => _isClearingCache = false);
    }
  }

  Future<void> _createInviteCode() async {
    final codeController = TextEditingController();
    final usesController = TextEditingController(text: '1');

    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.netflixCard,
        title: const Text('Créer un code d\'invitation', style: TextStyle(color: Colors.white)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: codeController,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Code (laisser vide pour auto-générer)',
                labelStyle: TextStyle(color: Colors.white60),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: usesController,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Nombre d\'utilisations max',
                labelStyle: TextStyle(color: Colors.white60),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Annuler', style: TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            onPressed: () async {
              final nav = Navigator.of(ctx);
              final messenger = ScaffoldMessenger.of(context);
              try {
                final maxUses = int.tryParse(usesController.text) ?? 1;
                final res = await apiClient.dio.post(
                  '/api/admin/invites',
                  data: {
                    if (codeController.text.trim().isNotEmpty)
                      'code': codeController.text.trim().toUpperCase(),
                    'max_uses': maxUses,
                  },
                );
                nav.pop();
                messenger.showSnackBar(
                  SnackBar(
                    content: Text('Code créé : ${res.data['code']}'),
                    backgroundColor: Colors.green,
                  ),
                );
              } catch (e) {
                messenger.showSnackBar(
                  SnackBar(content: Text('Erreur : $e')),
                );
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.netflixRed),
            child: const Text('Générer'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.netflixBlack,
      appBar: AppBar(
        title: const Text('Administration VidTele'),
        backgroundColor: Colors.black.withValues(alpha: 0.8),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Rafraîchir les stats',
            onPressed: _fetchStats,
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Cartes de statistiques serveur
            const Text(
              'Statistiques du Serveur',
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            if (_isLoadingStats)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: CircularProgressIndicator(color: AppTheme.netflixRed),
                ),
              )
            else if (_stats != null)
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                childAspectRatio: 1.6,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                children: [
                  _buildStatCard(
                    'Utilisateurs',
                    '${_stats!['total_users']}',
                    Icons.people_outline,
                    Colors.blueAccent,
                  ),
                  _buildStatCard(
                    'Vidéos Indexées',
                    '${_stats!['total_videos']}',
                    Icons.movie_outlined,
                    Colors.orangeAccent,
                  ),
                  _buildStatCard(
                    'Streams Actifs',
                    '${_stats!['active_streams']} / 15',
                    Icons.stream,
                    Colors.greenAccent,
                  ),
                  _buildStatCard(
                    'Cache Disque',
                    '${((_stats!['cache_size_mb'] ?? 0) / 1024).toStringAsFixed(1)} / ${_stats!['max_cache_gb']} Go',
                    Icons.storage_outlined,
                    Colors.purpleAccent,
                  ),
                ],
              ),
            const SizedBox(height: 24),

            // Actions d'administration
            const Text(
              'Actions Rapides',
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),

            // Bouton Synchroniser Telegram
            ListTile(
              tileColor: AppTheme.netflixCard,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              leading: _isSyncing
                  ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.netflixRed),
                    )
                  : const Icon(Icons.sync, color: Colors.white),
              title: const Text(
                'Synchroniser le Canal Telegram',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
              subtitle: const Text(
                'Scanne les nouveaux médias postés sur Telegram',
                style: TextStyle(color: Colors.white60, fontSize: 12),
              ),
              trailing: const Icon(Icons.chevron_right, color: Colors.white38),
              onTap: _isSyncing ? null : _triggerSync,
            ),
            if (_syncMessage != null) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.withValues(alpha: 0.15),
                  border: Border.all(color: Colors.green.withValues(alpha: 0.5)),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  _syncMessage!,
                  style: const TextStyle(color: Colors.greenAccent, fontSize: 13),
                ),
              ),
            ],
            const SizedBox(height: 12),

            // Bouton Générer Code d'invitation
            ListTile(
              tileColor: AppTheme.netflixCard,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              leading: const Icon(Icons.vpn_key_outlined, color: Colors.amber),
              title: const Text(
                'Générer un Code d\'Invitation',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
              subtitle: const Text(
                'Créer un code VIP pour un nouvel utilisateur',
                style: TextStyle(color: Colors.white60, fontSize: 12),
              ),
              trailing: const Icon(Icons.chevron_right, color: Colors.white38),
              onTap: _createInviteCode,
            ),
            const SizedBox(height: 12),

            // Bouton Purger Cache
            ListTile(
              tileColor: AppTheme.netflixCard,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              leading: _isClearingCache
                  ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.redAccent),
                    )
                  : const Icon(Icons.delete_sweep_outlined, color: Colors.redAccent),
              title: const Text(
                'Purger le Cache Vidéo',
                style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold),
              ),
              subtitle: const Text(
                'Supprime les fichiers temporaires pour libérer de l\'espace disque',
                style: TextStyle(color: Colors.white60, fontSize: 12),
              ),
              trailing: const Icon(Icons.chevron_right, color: Colors.white38),
              onTap: _isClearingCache ? null : _clearCache,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.netflixCard,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(title, style: const TextStyle(color: Colors.white70, fontSize: 12)),
              Icon(icon, color: color, size: 20),
            ],
          ),
          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}
