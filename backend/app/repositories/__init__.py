"""
Dépôts : accès aux données (requêtes SQLAlchemy), sans logique HTTP.

Règle d'architecture :
    routers/  -> reçoit la requête, valide, appelle un service ou un dépôt, formate la réponse
    services/ -> logique métier (streaming, cache, synchronisation...)
    repositories/ -> lecture/écriture en base, réutilisable et testable seul
"""
