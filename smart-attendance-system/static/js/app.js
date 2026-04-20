const translations = {
  en: {
    login_title: "Teacher/Admin Login",
    username_label: "Username",
    password_label: "Password",
    login_btn: "Login",
    dashboard_title: "Attendance Dashboard",
    dashboard_subtitle: "Simple, offline-first system for rural schools",
    total_students: "Total Students",
    today_present: "Marked Today",
    pending_sync: "Pending Sync",
    mark_attendance: "Mark Attendance",
    view_reports: "View Reports",
    add_students: "Add Students",
    class_overview: "Class Overview",
    students: "Students"
  },
  kn: {
    login_title: "ಶಿಕ್ಷಕ/ನಿರ್ವಹಣಾ ಲಾಗಿನ್",
    username_label: "ಬಳಕೆದಾರ ಹೆಸರು",
    password_label: "ಗುಪ್ತಪದ",
    login_btn: "ಲಾಗಿನ್",
    dashboard_title: "ಹಾಜರಾತಿ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್",
    dashboard_subtitle: "ಗ್ರಾಮೀಣ ಶಾಲೆಗಳಿಗಾಗಿ ಸರಳ ಆಫ್ಲೈನ್ ವ್ಯವಸ್ಥೆ",
    total_students: "ಒಟ್ಟು ವಿದ್ಯಾರ್ಥಿಗಳು",
    today_present: "ಇಂದು ಗುರುತಿಸಲಾಗಿದೆ",
    pending_sync: "ಸಿಂಕ್ ಬಾಕಿ",
    mark_attendance: "ಹಾಜರಾತಿ ಗುರುತು",
    view_reports: "ವರದಿಗಳು",
    add_students: "ವಿದ್ಯಾರ್ಥಿ ಸೇರಿಸಿ",
    class_overview: "ತರಗತಿ ಮಾಹಿತಿ",
    students: "ವಿದ್ಯಾರ್ಥಿಗಳು"
  }
};

function applyLanguage(lang) {
  const dict = translations[lang] || translations.en;
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });
}

function setLanguage(lang) {
  localStorage.setItem("lang", lang);
  applyLanguage(lang);
}

document.addEventListener("DOMContentLoaded", () => {
  const lang = localStorage.getItem("lang") || "en";
  applyLanguage(lang);
});
