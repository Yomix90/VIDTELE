/**
 * StreamAdmin JavaScript Framework
 * Gestion de l'interactivité : Sidebar, Multilingue FR/AR, Notifications Toast, etc.
 */

// 1. Gestion de la Sidebar (Pliage / Dépliage)
document.addEventListener("DOMContentLoaded", function () {
  const shell = document.getElementById("appShell");
  const toggleBtn = document.getElementById("sidebarToggle");

  if (toggleBtn && shell) {
    // Restaurer l'état précédent
    if (localStorage.getItem("streamadmin_sidebar_collapsed") === "true") {
      shell.classList.add("sidebar-collapsed");
    }

    toggleBtn.addEventListener("click", function () {
      shell.classList.toggle("sidebar-collapsed");
      const isCollapsed = shell.classList.contains("sidebar-collapsed");
      localStorage.setItem("streamadmin_sidebar_collapsed", isCollapsed);
    });
  }

  // Restaurer la langue
  initLanguage();
});

// 2. Gestion de la Langue (Bilinguisme FR / AR)
const I18N = {
  fr: {
    dashboard: "Tableau de bord",
    users: "Utilisateurs",
    invites: "Codes d'invitation",
    telegram: "Telegram",
    raw_videos: "Bibliothèque brute",
    series: "Séries",
    movies: "Films",
    mobile_home: "Accueil mobile",
    stats: "Statistiques",
    settings: "Paramètres",
    search_placeholder: "Rechercher une série, un film, un utilisateur, une vidéo Telegram...",
    logout: "Déconnexion",
    sync_btn: "Synchroniser Telegram",
    purge_cache: "Vider le cache",
    syncing: "Synchronisation en cours...",
    toast_success: "Opération réussie",
    toast_error: "Une erreur est survenue",
  },
  ar: {
    dashboard: "لوحة التحكم",
    users: "المستخدمون",
    invites: "رموز الدعوة",
    telegram: "تيليجرام",
    raw_videos: "المكتبة الخام",
    series: "المسلسلات",
    movies: "الأفلام",
    mobile_home: "واجهة التطبيق",
    stats: "الإحصائيات",
    settings: "الإعدادات",
    search_placeholder: "بحث عن مسلسل، فيلم، مستخدم، أو فيديو تيليجرام...",
    logout: "تسجيل الخروج",
    sync_btn: "مزامنة تيليجرام",
    purge_cache: "تفريغ الذاكرة المؤقتة",
    syncing: "جاري المزامنة...",
    toast_success: "تمت العملية بنجاح",
    toast_error: "حدث خطأ ما",
  }
};

function toggleLanguage() {
  const currentLang = localStorage.getItem("streamadmin_lang") || "fr";
  const newLang = currentLang === "fr" ? "ar" : "fr";
  setLanguage(newLang);
}

function setLanguage(lang) {
  localStorage.setItem("streamadmin_lang", lang);
  const html = document.documentElement;
  html.setAttribute("lang", lang);
  
  if (lang === "ar") {
    html.setAttribute("dir", "rtl");
    document.body.classList.add("rtl-mode");
    const langBtn = document.getElementById("langLabel");
    if (langBtn) langBtn.textContent = "Français";
  } else {
    html.setAttribute("dir", "ltr");
    document.body.classList.remove("rtl-mode");
    const langBtn = document.getElementById("langLabel");
    if (langBtn) langBtn.textContent = "العربية";
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
