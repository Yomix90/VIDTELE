/**
 * StreamAdmin JavaScript Framework
 * Gestion de l'interactivité : Sidebar, Multilingue FR/AR, Notifications Toast, etc.
 */

// 1. Gestion de la Sidebar (Pliage / Dépliage)
document.addEventListener("DOMContentLoaded", function () {
  const shell = document.getElementById("appShell");
  const toggleBtn = document.getElementById("sidebarToggle");

  if (toggleBtn && shell) {
    // Petit écran (< 992 px) : la barre latérale est un tiroir ouvert/fermé par le bouton ☰.
    // Grand écran : le bouton réduit/étend la barre (état mémorisé).
    const petitEcran = () => window.matchMedia("(max-width: 991.98px)").matches;

    let fond = shell.querySelector(".sidebar-backdrop");
    if (!fond) {
      fond = document.createElement("div");
      fond.className = "sidebar-backdrop";
      shell.appendChild(fond);
    }
    const fermerTiroir = () => shell.classList.remove("sidebar-open");
    fond.addEventListener("click", fermerTiroir);
    shell.querySelectorAll(".sidebar .nav-link").forEach((lien) =>
      lien.addEventListener("click", () => { if (petitEcran()) fermerTiroir(); })
    );
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") fermerTiroir(); });

    // Restaurer l'état précédent (grand écran uniquement)
    if (!petitEcran() && localStorage.getItem("streamadmin_sidebar_collapsed") === "true") {
      shell.classList.add("sidebar-collapsed");
    }

    toggleBtn.addEventListener("click", function () {
      if (petitEcran()) {
        shell.classList.toggle("sidebar-open");
        toggleBtn.setAttribute("aria-expanded", shell.classList.contains("sidebar-open"));
        return;
      }
      shell.classList.toggle("sidebar-collapsed");
      const isCollapsed = shell.classList.contains("sidebar-collapsed");
      localStorage.setItem("streamadmin_sidebar_collapsed", isCollapsed);
    });
  }

  // Restaurer la langue
  initLanguage();
});

// 2. Gestion de la Langue (Trilinguisme FR / EN / AR)
const I18N = {
  fr: {
    dashboard: "Tableau de bord",
    users: "Utilisateurs",
    invites: "Codes d'invitation",
    telegram: "Telegram MTProto",
    raw_videos: "Vidéos Brutes Telegram",
    series: "Séries & Épisodes",
    movies: "Films",
    mobile_home: "Éditeur Accueil Mobile",
    stats: "Statistiques",
    settings: "Paramètres & Mises à Jour",
    search_placeholder: "Rechercher une série, un film, un utilisateur, une vidéo Telegram...",
    logout: "Déconnexion",
    sync_btn: "Synchroniser Telegram",
    purge_cache: "Vider le cache",
    syncing: "Synchronisation en cours...",
    toast_success: "Opération réussie",
    toast_error: "Une erreur est survenue",
    cat_overview: "VUE D'ENSEMBLE",
    cat_catalog: "CATALOGUE & MÉDIAS",
    cat_infra: "RÉSEAU & STOCKAGE",
    cat_users: "UTILISATEURS & ACCÈS",
  },
  en: {
    dashboard: "Dashboard",
    users: "Users",
    invites: "Invite Codes",
    telegram: "Telegram MTProto",
    raw_videos: "Raw Telegram Videos",
    series: "TV Shows & Episodes",
    movies: "Movies",
    mobile_home: "Mobile Home Editor",
    stats: "Statistics",
    settings: "Settings & App Updates",
    search_placeholder: "Search TV shows, movies, users, or Telegram videos...",
    logout: "Log Out",
    sync_btn: "Sync Telegram",
    purge_cache: "Purge Cache",
    syncing: "Synchronizing in progress...",
    toast_success: "Action completed successfully",
    toast_error: "An error occurred",
    cat_overview: "OVERVIEW",
    cat_catalog: "CATALOG & MEDIA",
    cat_infra: "NETWORK & STORAGE",
    cat_users: "USERS & ACCESS",
  },
  ar: {
    dashboard: "لوحة التحكم",
    users: "المستخدمون",
    invites: "رموز الدعوة VIP",
    telegram: "تيليجرام MTProto",
    raw_videos: "المكتبة الخام تيليجرام",
    series: "المسلسلات والحلقات",
    movies: "الأفلام",
    mobile_home: "محرر واجهة التطبيق",
    stats: "الإحصائيات",
    settings: "الإعدادات والتحديثات",
    search_placeholder: "بحث عن مسلسل، فيلم، مستخدم، أو فيديو تيليجرام...",
    logout: "تسجيل الخروج",
    sync_btn: "مزامنة تيليجرام",
    purge_cache: "تفريغ الذاكرة المؤقتة",
    syncing: "جاري المزامنة...",
    toast_success: "تمت العملية بنجاح",
    toast_error: "حدث خطأ ما",
    cat_overview: "نظرة عامة",
    cat_catalog: "المكتبة والوسائط",
    cat_infra: "الشبكة والتخزين",
    cat_users: "المستخدمون والأمان",
  }
};

const LANG_LABELS = {
  fr: "🇫🇷 Français",
  en: "🇬🇧 English",
  ar: "🇲🇦 العربية"
};

function setLanguage(lang) {
  if (!["fr", "en", "ar"].includes(lang)) {
    lang = "fr";
  }
  localStorage.setItem("streamadmin_lang", lang);
  const html = document.documentElement;
  html.setAttribute("lang", lang);
  
  if (lang === "ar") {
    html.setAttribute("dir", "rtl");
    document.body.classList.add("rtl-mode");
  } else {
    html.setAttribute("dir", "ltr");
    document.body.classList.remove("rtl-mode");
  }

  const langLabel = document.getElementById("currentLangLabel");
  if (langLabel) {
    langLabel.textContent = LANG_LABELS[lang] || lang.toUpperCase();
  }

  // Mettre à jour les éléments annotés avec data-i18n
  document.querySelectorAll("[data-i18n]").forEach(function (el) {
    const key = el.getAttribute("data-i18n");
    if (I18N[lang] && I18N[lang][key]) {
      el.textContent = I18N[lang][key];
    }
  });

  // Mettre à jour le placeholder de recherche
  const searchInput = document.getElementById("globalSearchInput");
  if (searchInput && I18N[lang]) {
    searchInput.setAttribute("placeholder", I18N[lang].search_placeholder);
  }
}

function initLanguage() {
  const saved = localStorage.getItem("streamadmin_lang") || "fr";
  setLanguage(saved);
}

// 3. Notifications Toast
function showToast(message, type = "success") {
  let toastContainer = document.getElementById("toastContainer");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toastContainer";
    toastContainer.className = "toast-container position-fixed bottom-0 end-0 p-3";
    toastContainer.style.zIndex = "9999";
    document.body.appendChild(toastContainer);
  }

  const bgClass = type === "success" ? "bg-success text-white" : type === "error" || type === "danger" ? "bg-danger text-white" : "bg-dark text-white";
  const icon = type === "success" ? "bi-check-circle-fill" : type === "error" || type === "danger" ? "bi-exclamation-triangle-fill" : "bi-info-circle-fill";

  const toastId = "toast_" + Date.now();
  const toastHtml = `
    <div id="${toastId}" class="toast align-items-center ${bgClass} border-0 shadow-lg" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body d-flex align-items-center gap-2">
          <i class="bi ${icon} fs-5"></i>
          <div>${message}</div>
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>
  `;
  toastContainer.insertAdjacentHTML("beforeend", toastHtml);

  const toastEl = document.getElementById(toastId);
  if (window.bootstrap && window.bootstrap.Toast) {
    const bsToast = new bootstrap.Toast(toastEl, { delay: 4000 });
    bsToast.show();
    toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
  } else {
    setTimeout(() => toastEl.remove(), 4000);
  }
}

// 4. Lecteur Vidéo Streaming Intégré (Aperçu Admin HTTP 206)
async function playAdminVideo(videoId, title = "Aperçu Vidéo") {
  const modalEl = document.getElementById("videoPlayerModal");
  const videoEl = document.getElementById("adminGlobalVideoElement");
  const titleEl = document.getElementById("videoPlayerModalTitle");
  const infoEl = document.getElementById("videoPlayerInfo");
  const spinnerEl = document.getElementById("videoPlayerSpinner");

  if (!modalEl || !videoEl) {
    console.error("Lecteur vidéo introuvable dans le DOM.");
    return;
  }

  if (titleEl) titleEl.textContent = title;
  if (infoEl) infoEl.textContent = `Vidéo #${videoId} - Streaming natif Telegram`;
  if (spinnerEl) spinnerEl.style.display = "block";

  // Ouvrir immédiatement la modale avec le spinner
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();

  videoEl.onloadeddata = function() {
    if (spinnerEl) spinnerEl.style.display = "none";
  };
  videoEl.onerror = function() {
    if (spinnerEl) spinnerEl.style.display = "none";
    showToast("Impossible de charger le flux vidéo depuis Telegram.", "danger");
  };

  try {
    // 1. Obtenir un jeton signé valide pour cette vidéo (gère l'authentification admin automatiquement)
    const tokenRes = await fetch(`/api/videos/${videoId}/stream-token`);
    if (tokenRes.ok) {
      const tokenData = await tokenRes.json();
      videoEl.src = tokenData.stream_url || `/api/videos/${videoId}/stream?token=${tokenData.stream_token}`;
    } else {
      const errData = await tokenRes.json().catch(() => ({}));
      // Fallback direct sur l'URL de stream avec cookie
      videoEl.src = `/api/videos/${videoId}/stream`;
      if (errData.detail) {
        showToast(errData.detail, "warning");
      }
    }
  } catch (err) {
    videoEl.src = `/api/videos/${videoId}/stream`;
  }

  videoEl.play().catch(e => console.log("Autoplay bloqué ou en attente :", e));
}

function closeAdminVideo() {
  const videoEl = document.getElementById("adminGlobalVideoElement");
  if (videoEl) {
    videoEl.pause();
    videoEl.removeAttribute("src");
    videoEl.load();
  }
}

document.addEventListener("DOMContentLoaded", function () {
  const modalEl = document.getElementById("videoPlayerModal");
  if (modalEl) {
    modalEl.addEventListener("hidden.bs.modal", function () {
      closeAdminVideo();
    });
  }
});
