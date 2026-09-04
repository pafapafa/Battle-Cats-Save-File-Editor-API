'use strict';
(() => {
  const allowed = ['system', 'light', 'dark'];
  let preference = 'system';
  try { const stored = localStorage.getItem('bcsfe.docs.theme'); if (allowed.includes(stored)) preference = stored; } catch {}
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  function apply() {
    document.documentElement.dataset.theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
    document.documentElement.dataset.themePreference = preference;
  }
  window.docsTheme = {
    get: () => preference,
    set: value => {
      preference = allowed.includes(value) ? value : 'system';
      try { localStorage.setItem('bcsfe.docs.theme', preference); } catch {}
      apply();
    }
  };
  media.addEventListener('change', () => { if (preference === 'system') apply(); });
  apply();
})();
