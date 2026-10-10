# Guide Complet de Monétisation AdMob & Conformité Google Play (Atlas Play / VidTele)

Ce document détaille l'intégration technique de **Google Mobile Ads (`google_mobile_ads`)**, le cycle de vie des annonces vidéo avec récompense (**Rewarded Video Ads**), la gestion du consentement européen (**UMP / RGPD**) et la protection de votre compte contre la suspension.

---

## 1. Stratégie & Expérience Utilisateur

L'application diffuse des micro-séries et des vidéos courtes. La monétisation repose sur un modèle vertueux et non intrusif :

1. **Seuil aléatoire par cycle** : À chaque cycle, un seuil est tiré au sort de manière imprévisible entre **4 et 5 vidéos** (paramétrable dans `WatchGateController`).
2. **Critère de vidéo « regardée »** :
   - La vidéo doit avoir été visionnée à au moins **70 % de sa durée totale** (ou jusqu'à sa fin).
   - Les vidéos zappées rapidement en quelques secondes ne sont **pas comptabilisées**.
   - Chaque identifiant de vidéo unique n'est comptabilisé qu'une **seule fois** par cycle (revoir la même vidéo ne compte pas double).
3. **Obligation stricte de consentement (Règles AdMob & Google Play)** :
   - Une annonce récompensée n'est **JAMAIS** lancée automatiquement ni par surprise.
   - Au moment du seuil, la lecture est mise en pause et une feuille modale élégante (`AdGatePromptSheet`) propose :
     - **« Regarder la pub »** : lance l'annonce vidéo plein écran.
     - **« Plus tard »** : l'utilisateur peut différer, mais la vidéo suivante reste bloquée avec un overlay dédié (`AdGateLockedOverlay`) jusqu'au visionnage de l'annonce.
4. **Attribution stricte de la récompense** :
   - Le déblocage s'effectue **uniquement** si le callback Google `onUserEarnedReward` est validé.
   - Si l'utilisateur quitte la publicité avant la fin, rien n'est débloqué et l'application lui rappelle poliment qu'il doit aller jusqu'au bout.
5. **Persistance locale** :
   - L'état du quota, le seuil tiré, le verrouillage et les vidéos vues sont sauvegardés dans `SharedPreferences` et survivent aux redémarrages de l'application.
6. **Exemptions totales** :
   - Pas de publicité pour les comptes administrateurs (`role == 'admin'` ou `'super_admin'`).
   - Pas de publicité pour les comptes marqués VIP / Sans Pub (`ads_free == true`).
7. **Sécurité & Continuité de service** :
   - Si les serveurs AdMob ne renvoient aucune annonce après plusieurs tentatives (problème réseau temporaire ou inventaire épuisé), une dérogation d'urgence (`grantEmergencyBypass`) permet à l'utilisateur de continuer à regarder sans être pénalisé.

---

## 2. Identifiants AdMob (Android)

Les identifiants sont centralisés dans `mobile/lib/core/ads/ads_config.dart` et injectés dans `build.gradle.kts` :

### A. Mode Production (Version finale / Release)
- **ID d'application AdMob** : `ca-app-pub-7846348811801616~6697457552`
- **ID du bloc Rewarded (Annonce avec récompense)** : `ca-app-pub-7846348811801616/7954698905`

### B. Mode Développement / Test (Automatique en `kDebugMode`)
- **ID d'application de test Google** : `ca-app-pub-3940256099942544~3347511713`
- **ID du bloc Rewarded de test Google** : `ca-app-pub-3940256099942544/5224354917`

> [!IMPORTANT]
> En mode Debug (`flutter run`), l'application utilise **automatiquement les identifiants de test officiels de Google**. Vos vrais identifiants de production ne sont utilisés que lorsque vous compilez l'application en mode Release (`flutter build apk --release` ou `flutter build appbundle`).

---

## 3. Protection Anti-Suspension (Ne jamais cliquer sur ses propres pubs)

Cliquer sur ses propres publicités en production (ou générer des impressions artificielles) est la cause n°1 de bannissement définitif d'un compte AdMob par Google.

### Enregistrer votre smartphone physique comme Appareil de Test :
Lorsque vous installez une version Release sur votre téléphone pour faire des essais :
1. Lancez l'application et observez les logs via `flutter logs` ou Android Studio Logcat.
2. Recherchez un message ressemblant à :
   ```
   I/Ads: Use RequestConfiguration.Builder().setTestDeviceIds(Arrays.asList("33BE2250B43518CCDA7DE426D04EE231")) to get test ads on this device.
   ```
3. Copiez cet identifiant hexadécimal et ajoutez-le dans `mobile/lib/core/ads/ads_config.dart` :
   ```dart
   static const List<String> testDeviceIds = [
     '33BE2250B43518CCDA7DE426D04EE231', // Votre téléphone
   ];
   ```
4. Ainsi, même avec vos vrais identifiants en release, Google servira des annonces de test marquées "Test Ad" sur votre appareil, éliminant tout risque de suspension.

---

## 4. Consentement Européen (RGPD / UMP)

L'API **User Messaging Platform (UMP)** de Google est intégrée dans `mobile/lib/core/ads/consent_manager.dart` :

1. Au démarrage de l'application (`main.dart`), `ConsentManager.instance.requestConsent()` interroge Google pour savoir si l'utilisateur est situé dans l'Espace Économique Européen ou au Royaume-Uni.
2. Si le consentement est requis, la boîte de dialogue officielle Google s'affiche automatiquement.
3. **Configuration dans la console AdMob** :
   - Connectez-vous sur [Google AdMob](https://apps.admob.com/).
   - Allez dans **Confidentialité et messages** > **Règlement européen**.
   - Cliquez sur **Créer un message** et publiez le formulaire RGPD pour votre application.

---

## 5. Écran de Test & Diagnostic Intégré

L'application inclut un écran complet de diagnostic accessible directement depuis le menu :
**Profil > Paramètres > Outils Développeur / Diagnostic Publicités AdMob**
*(Cet écran est visible en mode Debug ou pour tout compte connecté avec le rôle Administrateur)*.

Cet écran permet de :
- Vérifier en direct l'App ID actif et le bloc publicitaire utilisé.
- Vérifier l'état du SDK AdMob (`IDLE`, `CHARGEMENT`, `PRÊTE À DIFFUSER`, etc.).
- Déclencher manuellement un préchargement d'annonce.
- Diffuser une annonce récompensée et tester l'attribution de la récompense.
- Simuler la lecture d'une vidéo à 70% et voir le compteur de quota s'incrémenter.
- Verrouiller ou réinitialiser le cycle WatchGate pour tester l'écran de blocage.
- Tester ou réinitialiser le formulaire de consentement UMP.

---

## 6. Endpoints Serveur (FastAPI)

Le backend fournit deux endpoints dédiés :

1. **`GET /api/config/ads`** :
   - Renvoie la configuration dynamique des annonces (`min_videos_per_cycle`, `max_videos_per_cycle`, `watch_completion_threshold`, `enabled`).
   - Renvoie automatiquement `enabled: false` pour les administrateurs et les comptes `ads_free: true`.
2. **`POST /api/analytics/ads`** :
   - Reçoit et journalise les événements publicitaires (`prompt_shown`, `reward_earned`, `ad_dismissed`, `ad_failed`) pour suivre les performances de monétisation.

---

## 7. Checklist Google Play Console avant Publication

Avant de publier votre mise à jour sur Google Play Console :

1. **Contenu de l'application > Publicités** :
   - Allez dans la Google Play Console > Votre application > **Contenu de l'application**.
   - Dans la section **Annonces**, sélectionnez : **« Oui, mon application contient des annonces »**.
2. **Déclaration de l'ID Publicitaire Android (AD_ID)** :
   - Dans **Contenu de l'application** > **Identifiant publicitaire**, déclarez que votre application utilise l'ID publicitaire pour la **publicité ou le marketing**.
   - La permission `com.google.android.gms.permission.AD_ID` est déjà inscrite dans votre `AndroidManifest.xml`.
3. **Génération du bundle de production** :
   ```bash
   cd mobile
   flutter build appbundle --release
   ```
   Le fichier optimisé prêt pour Google Play se trouvera dans `build/app/outputs/bundle/release/app-release.aab`.
