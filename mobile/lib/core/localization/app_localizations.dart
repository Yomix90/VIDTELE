import 'package:flutter/material.dart';

/// Système complet de localisation trilingue (Français, Anglais, Arabe avec support RTL complet).
class AppLocalizations {
  final Locale locale;

  AppLocalizations(this.locale);

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations) ??
        AppLocalizations(const Locale('fr'));
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  String get langCode => locale.languageCode;
  bool get isArabic => langCode == 'ar';
  bool get isEnglish => langCode == 'en';
  bool get isFrench => langCode == 'fr';

  // ==================== AUTH & LOGIN ====================
  String get appTitle => 'Atlas Play';
  String get welcomeTitle => isArabic
      ? 'مرحبًا بك في Atlas Play'
      : (isEnglish ? 'Welcome to Atlas Play' : 'Bienvenue sur Atlas Play');
  String get welcomeSubtitle => isArabic
      ? 'بث فيديو خاص فائق السرعة على طريقة نتفليكس'
      : (isEnglish
          ? 'Private high-speed cinematic streaming'
          : 'Streaming privé cinématique haute vitesse');
  String get signIn => isArabic
      ? 'تسجيل الدخول'
      : (isEnglish ? 'Sign In' : 'Connexion');
  String get signUpVip => isArabic
      ? 'تسجيل حساب VIP'
      : (isEnglish ? 'VIP Registration' : 'Inscription VIP');
  String get username => isArabic
      ? 'اسم المستخدم'
      : (isEnglish ? 'Username' : 'Nom d\'utilisateur');
  String get password => isArabic
      ? 'كلمة المرour'
      : (isEnglish ? 'Password' : 'Mot de passe');
  String get inviteCodeVip => isArabic
      ? 'رمز الدعوة (VIP)'
      : (isEnglish ? 'Invitation Code (VIP)' : 'Code d\'invitation (VIP)');
  String get connectButton => isArabic
      ? 'دخول'
      : (isEnglish ? 'Sign In' : 'Se connecter');
  String get registerButton => isArabic
      ? 'إنشاء حساب باستخدام رمز VIP'
      : (isEnglish
          ? 'Register with VIP Code'
          : 'S\'inscrire avec le code VIP');
  String get noAccountPrompt => isArabic
      ? 'ليس لديك حساب؟ إنشاء حساب'
      : (isEnglish
          ? 'Don\'t have an account? Sign Up'
          : 'Pas encore de compte ? S\'inscrire');
  String get alreadyAccountPrompt => isArabic
      ? 'لديك حساب بالفعل؟ تسجيل الدخول'
      : (isEnglish
          ? 'Already have an account? Sign In'
          : 'Déjà un compte ? Se connecter');
  String get fillAllFields => isArabic
      ? 'يرجى ملء جميع الحقول المطلوبة'
      : (isEnglish
          ? 'Please fill in all required fields'
          : 'Veuillez remplir tous les champs obligatoires');
  String get configureBackendServer => isArabic
      ? 'تهيئة عنوان الخادم'
      : (isEnglish
          ? 'Configure Backend Server'
          : 'Configurer le serveur backend');
  String get serverUrlDialogTitle => isArabic
      ? 'عنوان خادم الواجهة الخلفية'
      : (isEnglish
          ? 'Backend Server URL'
          : 'Adresse du Serveur Backend');
  String get serverUrlDialogDesc => isArabic
      ? 'أدخل عنوان IP والمنفذ لخادم VPS الخاص بك أو جهازك المحلي (مثال: http://192.168.1.50:8000)'
      : (isEnglish
          ? 'Enter your VPS or local machine IP and port (e.g. http://192.168.1.50:8000)'
          : 'Entrez l\'adresse IP et le port de votre VPS ou machine locale (ex: http://192.168.1.50:8000)');
  String get cancel => isArabic ? 'إلغاء' : (isEnglish ? 'Cancel' : 'Annuler');
  String get save => isArabic ? 'حفظ' : (isEnglish ? 'Save' : 'Enregistrer');
  String serverUpdated(String url) => isArabic
      ? 'تم تحديث عنوان الخادم: $url'
      : (isEnglish ? 'Server updated: $url' : 'Serveur mis à jour : $url');

  // ==================== NAVIGATION BAR ====================
  String get navHome => isArabic ? 'الرئيسية' : (isEnglish ? 'Home' : 'Accueil');
  String get navDiscover => isArabic ? 'اكتشف' : (isEnglish ? 'Discover' : 'Découvrir');
  String get navSearch => isArabic ? 'بحث' : (isEnglish ? 'Search' : 'Recherche');
  String get navMyList => isArabic ? 'قائمتي' : (isEnglish ? 'My List' : 'Ma Liste');
  String get navProfile => isArabic ? 'حسابي' : (isEnglish ? 'Profile' : 'Profil');
  String get navReels => navDiscover;
  String get navHistory => isArabic ? 'السجل' : (isEnglish ? 'History' : 'Historique');
  String get navSettings => isArabic ? 'الإعدادات' : (isEnglish ? 'Settings' : 'Paramètres');
  String get latestSeriesTitle => isArabic ? 'أحدث المسلسلات المضافة' : (isEnglish ? 'Latest Added Series' : 'Dernières Séries Ajoutées');
  String get series => isArabic ? 'مسلسلات' : (isEnglish ? 'TV Shows' : 'Séries TV');

  // ==================== HOME SCREEN ====================
  String get searchPlaceholder => isArabic
      ? 'البحث عن فيلم، مسلسل، وسم...'
      : (isEnglish
          ? 'Search movies, series, hashtags...'
          : 'Rechercher un film, une série, un hashtag...');
  String get search => isArabic ? 'بحث' : (isEnglish ? 'Search' : 'Recherche');
  String get searchResultsTitle => isArabic
      ? 'نتائج البحث'
      : (isEnglish ? 'Search Results' : 'Résultats de recherche');
  String noResultsFor(String query) => isArabic
      ? 'لا توجد نتائج تطابق "$query"'
      : (isEnglish
          ? 'No results found for "$query"'
          : 'Aucun résultat trouvé pour "$query"');
  String get play => isArabic ? 'تشغيل' : (isEnglish ? 'Play' : 'Lecture');
  String get details => isArabic ? 'تفاصيل' : (isEnglish ? 'Details' : 'Détails');
  String get continueWatching => isArabic
      ? 'متابعة المشاهدة'
      : (isEnglish ? 'Continue Watching' : 'Continuer la lecture');
  String get top5Trending => isArabic
      ? 'أفضل 5 مقاطع الأكثر مشاهدة'
      : (isEnglish
          ? 'Top 5 Most Watched Videos'
          : 'Top 5 des Vidéos les plus regardées');
  String get top5Series => isArabic
      ? 'أفضل 5 مسلسلات'
      : (isEnglish ? 'Top 5 Series' : 'Top 5 des Séries');
  String get newReleases => isArabic
      ? 'أحدث الإصدارات'
      : (isEnglish ? 'New Releases' : 'Nouveautés');
  String get trendingNow => isArabic
      ? 'الأكثر رواجاً'
      : (isEnglish ? 'Trending Now' : 'Tendances du moment');
  String get recommendedForYou => isArabic
      ? 'موصى به لك'
      : (isEnglish ? 'Recommended for you' : 'Recommandé pour vous');
  String get refresh => isArabic ? 'تحديث' : (isEnglish ? 'Refresh' : 'Rafraîchir');
  String get retry => isArabic ? 'إعادة المحاولة' : (isEnglish ? 'Retry' : 'Réessayer');
  String get catalogLoadError => isArabic
      ? 'تعذر تحميل قائمة الفيديوهات'
      : (isEnglish
          ? 'Failed to load video catalog'
          : 'Impossible de charger le catalogue');

  // ==================== VIDEO PLAYER ====================
  String get loadingStream => isArabic
      ? 'جاري تحميل دفق الفيديو...'
      : (isEnglish ? 'Loading video stream...' : 'Chargement du flux vidéo...');
  String get playbackErrorTitle => isArabic
      ? 'خطأ في التشغيل'
      : (isEnglish ? 'Playback Error' : 'Erreur de lecture');
  String get streamLimitReached => isArabic
      ? 'تم بلوغ الحد الأقصى للبث المتزامن (15 على الخادم أو 2 لكل حساب). يرجى الانتظار حتى تنتهي جلسة أخرى.'
      : (isEnglish
          ? 'Concurrent stream limit reached (max 15 on server or 2 per account). Please wait for an active stream to finish.'
          : 'Limite de flux simultanés atteinte (15 max sur le serveur ou 2 par compte). Veuillez patienter qu\'une session se libère.');
  String get videoNotFound => isArabic
      ? 'هذا الفيديو لم يعد متوفراً في قناة تيليغرام.'
      : (isEnglish
          ? 'This video is no longer available on the Telegram channel.'
          : 'Cette vidéo n\'est plus disponible sur le canal Telegram.');
  String get cannotPlayVideo => isArabic
      ? 'تعذر تشغيل الفيديو'
      : (isEnglish ? 'Cannot play video' : 'Impossible de lancer la vidéo');
  String get episodesList => isArabic ? 'قائمة الحلقات' : (isEnglish ? 'Episodes List' : 'Liste des épisodes');
  String get nextEpisode => isArabic ? 'الحلقة التالية' : (isEnglish ? 'Next Episode' : 'Épisode suivant');
  String get playbackSpeed => isArabic ? 'سرعة التشغيل' : (isEnglish ? 'Playback Speed' : 'Vitesse de lecture');
  String get noReelsAvailable => isArabic
      ? 'لا توجد حلقات متوفرة في الموجز'
      : (isEnglish ? 'No episodes available in the feed' : 'Aucun épisode disponible dans le flux');


  // ==================== MY LIST (FAVORITES) ====================
  String get myListTitle => isArabic ? 'قائمتي' : (isEnglish ? 'My List' : 'Ma Liste');
  String get myListEmptyTitle => isArabic
      ? 'قائمتك فارغة'
      : (isEnglish ? 'Your list is empty' : 'Votre liste est vide');
  String get myListEmptySubtitle => isArabic
      ? 'أضف الأفلام والمسلسلات المفضلة لديك للوصول إليها بسهولة ومشاهدتها لاحقًا.'
      : (isEnglish
          ? 'Add movies and series to your list to easily find and watch them later.'
          : 'Ajoutez des films et séries à votre liste pour les retrouver facilement et les regarder plus tard.');
  String get favoritesLoadError => isArabic
      ? 'تعذر تحميل قائمتك المفضلة'
      : (isEnglish ? 'Failed to load your list' : 'Impossible de charger vos favoris');

  // ==================== HISTORY ====================
  String get historyTitle => isArabic
      ? 'سجل المشاهدة'
      : (isEnglish ? 'Watch History' : 'Historique de lecture');
  String get historyEmptyTitle => isArabic
      ? 'لا يوجد سجل مشاهدة حتى الآن'
      : (isEnglish ? 'No watch history yet' : 'Aucun historique de visionnage');
  String get historyEmptySubtitle => isArabic
      ? 'ستظهر هنا مقاطع الفيديو التي تشاهدها مع نسبة التقدم لمواصلة المشاهدة من حيث توقفت.'
      : (isEnglish
          ? 'Videos you watch will appear here with your progress to resume right where you left off.'
          : 'Les vidéos que vous regardez apparaîtront ici avec votre progression pour reprendre là où vous vous êtes arrêté.');
  String get watchedBadge => isArabic
      ? 'تمت المشاهدة'
      : (isEnglish ? 'Watched' : 'Visionné');
  String percentCompleted(int percent) => isArabic
      ? '$percent% مكتمل'
      : (isEnglish ? '$percent% completed' : '$percent% terminé');

  // ==================== SETTINGS & PROFILE ====================
  String get settingsTitle => isArabic
      ? 'الإعدادات والملف الشخصي'
      : (isEnglish ? 'Settings & Profile' : 'Paramètres & Profil');
  String get defaultUsername => isArabic ? 'المستخدم' : (isEnglish ? 'User' : 'Utilisateur');
  String get roleAdminBadge => isArabic
      ? 'مسؤول النظام'
      : (isEnglish ? 'ADMINISTRATOR' : 'ADMINISTRATEUR');
  String get roleVipBadge => isArabic
      ? 'عضو VIP'
      : (isEnglish ? 'VIP MEMBER' : 'MEMBRE VIP');
  String get preferencesHeader => isArabic
      ? 'التفضيلات العامة'
      : (isEnglish ? 'General Preferences' : 'Préférences Générales');
  String get languageOption => isArabic
      ? 'لغة العرض'
      : (isEnglish ? 'Display Language' : 'Langue d\'affichage');
  String get displayLanguage => languageOption;
  String get currentLangName => isArabic
      ? 'العربية (من اليمين لليسار)'
      : (isEnglish ? 'English' : 'Français');
  String get serverAddressOption => isArabic
      ? 'عنوان خادم الواجهة الخلفية'
      : (isEnglish ? 'Backend Server Address' : 'Adresse du Serveur Backend');
  String get editServerAddressTitle => isArabic
      ? 'تعديل رابط الخادم'
      : (isEnglish ? 'Edit Server URL' : 'Modifier l\'URL du serveur');
  String get adminPanelHeader => isArabic
      ? 'إدارة المنصة'
      : (isEnglish ? 'Administration Panel' : 'Panneau d\'Administration');
  String get adminServerAndSync => isArabic
      ? 'لوحة التحكم والعمليات'
      : (isEnglish
          ? 'Server Operations & Sync'
          : 'Gestion du Serveur & Sync');
  String get adminServerAndSyncDesc => isArabic
      ? 'المزامنة مع تيليغرام، رموز الدعوة، وتفريغ الذاكرة'
      : (isEnglish
          ? 'Telegram sync, VIP invites, cache management'
          : 'Synchronisation Telegram, invitations VIP, cache');
  String get appVersionInfo => 'Atlas Play Mobile v1.0.0 (Production)';
  String get engineInfo => isArabic
      ? 'محرك بث MTProto عبر HTTP 206 مجزأ بدون تأخير'
      : (isEnglish
          ? 'Atlas Play high-performance streaming engine'
          : 'Moteur Atlas Play Streaming HTTP 206 partiel');
  String get checkUpdateTitle => isArabic
      ? 'تحديث التطبيق'
      : (isEnglish ? 'App Update' : 'Mise à jour de l\'application');
  String get updateAvailablePrompt => isArabic
      ? 'إصدار جديد متوفر الآن!'
      : (isEnglish ? 'A new version is available!' : 'Une nouvelle version est disponible !');
  String get updateNowButton => isArabic
      ? 'تحديث الآن'
      : (isEnglish ? 'Update Now' : 'Mettre à jour');
  String get updateRequiredTitle => isArabic
      ? 'التحديث مطلوب'
      : (isEnglish ? 'Update required' : 'Mise à jour requise');
  String get updateRequiredMessage => isArabic
      ? 'هذا الإصدار من التطبيق لم يعد مدعومًا. يرجى تثبيت الإصدار الجديد للمتابعة.'
      : (isEnglish
          ? 'This version of the app is no longer supported. Please install the new version to continue.'
          : "Cette version de l'application n'est plus prise en charge. Installez la nouvelle version pour continuer.");
  String minimumVersionLabel(String version) => isArabic
      ? 'الإصدار الأدنى: $version'
      : (isEnglish ? 'Minimum version: $version' : 'Version minimale : $version');
  String get laterButton => isArabic
      ? 'لاحقًا'
      : (isEnglish ? 'Later' : 'Plus tard');
  String get logOutButton => isArabic
      ? 'تسجيل الخروج'
      : (isEnglish ? 'Log Out' : 'Se déconnecter');
  String get confirmLogoutTitle => isArabic
      ? 'تأكيد تسجيل الخروج؟'
      : (isEnglish ? 'Confirm Log Out?' : 'Confirmer la déconnexion ?');
  String get confirmLogoutMessage => isArabic
      ? 'هل أنت متأكد من رغبتك في تسجيل الخروج من هذا الجهاز؟'
      : (isEnglish
          ? 'Are you sure you want to exit your current session on this device?'
          : 'Êtes-vous sûr de vouloir quitter votre session actuelle sur cet appareil ?');

  // ==================== ADMIN PANEL ====================
  String get adminScreenTitle => isArabic
      ? 'إدارة Atlas Play'
      : (isEnglish ? 'Atlas Play Administration' : 'Administration Atlas Play');
  String get serverStatsHeader => isArabic
      ? 'إحصائيات الخادم'
      : (isEnglish ? 'Server Statistics' : 'Statistiques du Serveur');
  String get statUsers => isArabic ? 'المستخدمون' : (isEnglish ? 'Users' : 'Utilisateurs');
  String get statVideos => isArabic
      ? 'مقاطع الفيديو'
      : (isEnglish ? 'Indexed Videos' : 'Vidéos Indexées');
  String get statStreams => isArabic
      ? 'جلسات البث'
      : (isEnglish ? 'Active Streams' : 'Streams Actifs');
  String get statCache => isArabic
      ? 'الذاكرة المؤقتة'
      : (isEnglish ? 'Disk Cache' : 'Cache Disque');
  String get quickActionsHeader => isArabic
      ? 'الإجراءات السريعة'
      : (isEnglish ? 'Quick Actions' : 'Actions Rapides');
  String get syncTelegramAction => isArabic
      ? 'مزامنة قناة تيليغرام'
      : (isEnglish
          ? 'Sync Telegram Channel'
          : 'Synchroniser le Canal Telegram');
  String get syncTelegramDesc => isArabic
      ? 'فحص المقاطع والوسائط الجديدة المنشورة على تيليغرام'
      : (isEnglish
          ? 'Scans newly posted videos and media on Telegram'
          : 'Scanne les nouveaux médias postés sur Telegram');
  String get generateInviteAction => isArabic
      ? 'إنشاء رمز دعوة'
      : (isEnglish
          ? 'Generate Invitation Code'
          : 'Générer un Code d\'Invitation');
  String get generateInviteDesc => isArabic
      ? 'إنشاء رمز VIP لمستخدم جديد'
      : (isEnglish
          ? 'Create a VIP code for a new user'
          : 'Créer un code VIP pour un nouvel utilisateur');
  String get clearCacheAction => isArabic
      ? 'تفريغ ذاكرة الفيديو المؤقتة'
      : (isEnglish ? 'Clear Video Cache' : 'Purger le Cache Vidéo');
  String get clearCacheDesc => isArabic
      ? 'حذف الملفات المؤقتة لتوفير مساحة على القرص الصلب'
      : (isEnglish
          ? 'Deletes temporary video files to free up disk space'
          : 'Supprime les fichiers temporaires pour libérer de l\'espace disque');
  String get clearCacheConfirmTitle => isArabic
      ? 'تفريغ الذاكرة المؤقتة للقرص؟'
      : (isEnglish ? 'Clear local video cache?' : 'Purger le cache local ?');
  String get clearCacheConfirmDesc => isArabic
      ? 'سيتم حذف ملفات الفيديو المؤقتة من الخادم. وسيتم إعادة تنزيلها تلقائيًا عند المشاهدة القادمة.'
      : (isEnglish
          ? 'Cached video files will be removed from server disk. They will be downloaded automatically on next view.'
          : 'Les fichiers vidéo mis en cache seront supprimés du serveur. Ils seront re-téléchargés automatiquement à la prochaine lecture.');
  String get clearButton => isArabic ? 'تفريغ' : (isEnglish ? 'Clear' : 'Purger');
  String get cacheClearedSuccess => isArabic
      ? 'تم تفريغ الذاكرة المؤقتة بنجاح!'
      : (isEnglish
          ? 'Cache cleared successfully!'
          : 'Cache purgé avec succès !');
  String get createInviteModalTitle => isArabic
      ? 'إنشاء رمز دعوة جديد'
      : (isEnglish
          ? 'Create New Invitation Code'
          : 'Créer un code d\'invitation');
  String get inviteCodeInputLabel => isArabic
      ? 'الرمز (اتركه فارغاً للتوليد التلقائي)'
      : (isEnglish
          ? 'Code (leave blank to auto-generate)'
          : 'Code (laisser vide pour auto-générer)');
  String get maxUsesInputLabel => isArabic
      ? 'أقصى عدد للاستخدام'
      : (isEnglish
          ? 'Maximum uses count'
          : 'Nombre d\'utilisations max');
  String get generateButton => isArabic
      ? 'توليد'
      : (isEnglish ? 'Generate' : 'Générer');
  String inviteCreatedSuccess(String code) => isArabic
      ? 'تم إنشاء الرمز بنجاح: $code'
      : (isEnglish ? 'Code created: $code' : 'Code créé : $code');
  String syncSuccessMessage(int added, int updated, int scanned) => isArabic
      ? 'تمت المزامنة بنجاح! +$added مضاف، $updated محدث ($scanned رسالة مفحوصة).'
      : (isEnglish
          ? 'Sync successful! +$added added, $updated updated ($scanned messages scanned).'
          : 'Sync réussie ! +$added ajoutées, $updated mises à jour ($scanned messages scannés).');

  // ==================== SÉRIES, MA LISTE & RECHERCHE ====================
  String get similarSeries => isArabic
      ? 'أعمال مشابهة'
      : (isEnglish ? 'Similar Titles' : 'Titres similaires');
  String get addedToMyList => isArabic
      ? 'تمت الإضافة إلى قائمتي'
      : (isEnglish ? 'Added to My List' : 'Ajouté à Ma liste');
  String get removedFromMyList => isArabic
      ? 'تمت الإزالة من قائمتي'
      : (isEnglish ? 'Removed from My List' : 'Retiré de Ma liste');
  String get expand => isArabic ? 'المزيد' : (isEnglish ? 'More' : 'Plus');
  String get collapse => isArabic ? 'أقل' : (isEnglish ? 'Less' : 'Moins');
  String get filterAll => isArabic ? 'الكل' : (isEnglish ? 'All' : 'Tout');
  String get filterSeries => isArabic ? 'مسلسلات' : (isEnglish ? 'Series' : 'Séries');
  String get filterInProgress => isArabic ? 'قيد المشاهدة' : (isEnglish ? 'In Progress' : 'En cours');
  String get episodesHeader => isArabic ? 'الحلقات' : (isEnglish ? 'Episodes' : 'Épisodes');
  String get seriesCompletedTitle => isArabic ? 'سلسلة مكتملة !' : (isEnglish ? 'Series Completed!' : 'Série terminée !');
  String get seriesCompletedSubtitle => isArabic
      ? 'تهانينا! لقد شاهدت جميع حلقات هذه السلسلة.'
      : (isEnglish
          ? 'Congratulations! You have watched all episodes of this series.'
          : 'Félicitations ! Vous avez regardé tous les épisodes de cette série.');
  String get recommendedSeries => isArabic ? 'مسلسلات مقترحة لك' : (isEnglish ? 'Recommended Series' : 'Séries recommandées pour vous');
  String get restartSeries => isArabic ? 'إعادة المشاهدة من البداية' : (isEnglish ? 'Restart Series' : 'Recommencer la série');
  String get backToHome => isArabic ? 'العودة للرئيسية' : (isEnglish ? 'Back to Home' : 'Retour à l\'accueil');

  // ==================== MONETIZATION / REWARDED ADS ====================
  String get adRewardPromptTitle => isArabic
      ? 'فتح المزيد من مقاطع الفيديو'
      : (isEnglish ? 'Unlock More Videos' : 'Débloquer plus de vidéos');

  String adRewardPromptMessage(int count) => isArabic
      ? 'شاهد إعلاناً قصيراً لفتح $count مقاطع فيديو جديدة مجاناً.'
      : (isEnglish
          ? 'Watch a short video ad to unlock $count more videos for free.'
          : 'Regardez une courte vidéo publicitaire pour débloquer $count vidéos de plus.');

  String get adWatchButton => isArabic
      ? 'مشاهدة الإعلان'
      : (isEnglish ? 'Watch Ad' : 'Regarder la pub');

  String get adLaterButton => isArabic
      ? 'لاحقاً'
      : (isEnglish ? 'Later' : 'Plus tard');

  String get adNotCompletedWarning => isArabic
      ? 'يجب مشاهدة الإعلان حتى النهاية لفتح مقاطع الفيديو.'
      : (isEnglish
          ? 'You must watch the ad until the end to unlock videos.'
          : 'Vous devez regarder la pub jusqu\'à la fin pour débloquer les vidéos.');

  String get adGateLockedTitle => isArabic
      ? 'تم الوصول إلى حد المشاهدة'
      : (isEnglish ? 'Watch Limit Reached' : 'Limite de visionnage atteinte');

  String get adGateLockedMessage => isArabic
      ? 'لقد شاهدت حصتك من مقاطع الفيديو. شاهد إعلاناً قصيراً لمتابعة المشاهدة.'
      : (isEnglish
          ? 'You reached your free watch limit. Watch a short ad to continue.'
          : 'Vous avez atteint votre quota de vidéos. Regardez une courte pub pour continuer.');

  String get adUnavailableMessage => isArabic
      ? 'لا يوجد إعلان متاح حالياً. يرجى المحاولة بعد قليل.'
      : (isEnglish
          ? 'No ad available right now. Please try again in a moment.'
          : 'Aucune annonce disponible actuellement. Veuillez réessayer dans un instant.');

  // ==================== PLAYER & AUTO-HIDE ====================
  String get playbackPreferencesHeader => isArabic
      ? 'إعدادات التشغيل'
      : (isEnglish ? 'Playback Preferences' : 'Préférences de Lecture');
  String get autoHideControlsTitle => isArabic
      ? 'إخفاء الأزرار تلقائياً'
      : (isEnglish ? 'Auto-hide controls' : 'Masquer automatiquement les boutons');
  String get autoHideControlsDesc => isArabic
      ? 'إخفاء أزرار التحكم بعد بدء التشغيل لتجربة سينمائية نقية'
      : (isEnglish
          ? 'Hide controls after playback starts for a cinematic experience'
          : 'Faire disparaître les boutons pour une expérience cinéma immersive');
  String get autoHideDelayTitle => isArabic
      ? 'مدة بقاء الأزرار'
      : (isEnglish ? 'Controls display duration' : 'Durée d\'affichage des boutons');
  String autoHideSecondsSummary(int sec) => isArabic
      ? '$sec ثوانٍ'
      : (isEnglish ? '$sec seconds' : '$sec secondes');

  // ==================== FORMATTERS ====================
  String formatDuration(int seconds) {
    if (seconds <= 0) {
      return isArabic
          ? 'مقطع قصير'
          : (isEnglish ? 'Short clip' : 'Court clip');
    }
    final minutes = seconds ~/ 60;
    final remSeconds = seconds % 60;
    if (minutes >= 60) {
      final hours = minutes ~/ 60;
      final remMin = minutes % 60;
      return isArabic
          ? '$hours س $remMin د'
          : (isEnglish ? '${hours}h ${remMin}m' : '${hours}h ${remMin}m');
    }
    return isArabic
        ? '$minutes د $remSeconds ث'
        : (isEnglish ? '${minutes}m ${remSeconds}s' : '${minutes}m ${remSeconds}s');
  }
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) {
    return ['fr', 'en', 'ar'].contains(locale.languageCode);
  }

  @override
  Future<AppLocalizations> load(Locale locale) async {
    return AppLocalizations(locale);
  }

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

/// Extension sur BuildContext pour un accès concis: context.l10n
extension LocalizedContext on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this);
}
