(() => {
  const FOCUSABLE_SELECTOR = [
    'a[href]:not([tabindex="-1"])',
    'button:not([disabled]):not([tabindex="-1"])',
    'input:not([disabled]):not([tabindex="-1"])',
    'select:not([disabled]):not([tabindex="-1"])',
    'textarea:not([disabled]):not([tabindex="-1"])',
    '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  function visibleFocusable(root) {
    return Array.from(root.querySelectorAll(FOCUSABLE_SELECTOR)).filter(element => {
      if (!(element instanceof HTMLElement)) return false;
      const style = window.getComputedStyle(element);
      return style.visibility !== 'hidden' && style.display !== 'none';
    });
  }

  function mount() {
    const view = document.getElementById('mw-view');
    if (!view || view.dataset.a11yReady === 'true') return;

    view.dataset.a11yReady = 'true';
    let opener = null;

    const rememberAndFocus = event => {
      if (!(event.currentTarget instanceof HTMLElement)) return;
      opener = event.currentTarget;
      queueMicrotask(() => {
        if (!view.hidden) document.getElementById('mw-close')?.focus();
      });
    };

    ['mw-open', 'mw-open-media'].forEach(id => {
      document.getElementById(id)?.addEventListener('click', rememberAndFocus);
    });

    view.addEventListener('keydown', event => {
      if (event.key !== 'Tab' || view.hidden) return;
      const focusable = visibleFocusable(view);
      if (!focusable.length) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    });

    if ('MutationObserver' in window) {
      const observer = new MutationObserver(() => {
        if (view.hidden) {
          if (opener?.isConnected) opener.focus();
          return;
        }
        queueMicrotask(() => document.getElementById('mw-close')?.focus());
      });
      observer.observe(view, { attributes: true, attributeFilter: ['hidden'] });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => queueMicrotask(mount), { once: true });
  } else {
    queueMicrotask(mount);
  }
})();
