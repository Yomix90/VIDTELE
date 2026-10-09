/// Modèle représentant une catégorie / collection de vidéos.
class CategoryModel {
  final String name;
  final int count;

  CategoryModel({
    required this.name,
    required this.count,
  });

  factory CategoryModel.fromJson(Map<String, dynamic> json) {
    return CategoryModel(
      name: json['name'] ?? 'Général',
      count: json['count'] ?? 0,
    );
  }
}
