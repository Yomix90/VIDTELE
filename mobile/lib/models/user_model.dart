/// Modèle représentant un utilisateur authentifié.
class UserModel {
  final int id;
  final String username;
  final String role;
  final bool isActive;
  final int maxConcurrentStreams;

  UserModel({
    required this.id,
    required this.username,
    required this.role,
    required this.isActive,
    required this.maxConcurrentStreams,
  });

  bool get isAdmin => role == 'admin';

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] ?? json['user_id'] ?? 0,
      username: json['username'] ?? '',
      role: json['role'] ?? 'user',
      isActive: json['is_active'] ?? true,
      maxConcurrentStreams: json['max_concurrent_streams'] ?? 2,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'role': role,
      'is_active': isActive,
      'max_concurrent_streams': maxConcurrentStreams,
    };
  }
}
