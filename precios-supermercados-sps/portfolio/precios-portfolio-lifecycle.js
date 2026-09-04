(() => {
  const CARD_SELECTOR = '[data-portfolio-project="precios-supermercados"].price-card';
  let lastOpener = null;

  function api() {
    return window.PortfolioI18n;
  }

  function t(key) {
    return api()?.t(`prices.${key}`) || key;
  }

  function setText(root, selector, key) {
    const element = root?.querySelector(selector);
    if (element) element.textContent = t(key);
  }

  function refreshCard() {
    const card = document.querySelector(CARD_SELECTOR);
    if (!card || !api()) return;

    const labels = card.querySelectorAll('.price-card__signal small');
    ['card.preview.sources', 'card.preview.locations', 'card.preview.products', 'card.preview.cities']
      .forEach((key, index) => {
        if (labels[index]) labels[index].textContent = t(key);
      });

    card.querySelectorAll('[data-price-open]').forEach(control => {
      if (control.classList.contains('price-card__preview')) {
        control.setAttribute('aria-label', t('card.previewLabel'));
      }
    });
    setText(card, 'h3', 'card.title');
    setText(card, '.price-card__content > p', 'card.body');
    setText(card, '.price-card__actions [data-price-open]', 'card.open');
    setText(card, '.price-card__actions a', 'card.repo');
  }

  function openFrom(control) {
    const dialog = document.getElementById('price-project-view');
    if (!(dialog instanceof HTMLDialogElement)) return;
    lastOpener = control;
    if (!dialog.open) dialog.showModal();
    document.body.classList.add('is-locked');
    dialog.scrollTop = 0;
    dialog.querySelector('[data-price-close]')?.focus();
  }

  function mount() {
    refreshCard();

    document.addEventListener('click', event => {
      const control = event.target.closest(`${CARD_SELECTOR} [data-price-open]`);
      if (control) openFrom(control);
    });

    window.addEventListener('portfolio:localechange', () => queueMicrotask(refreshCard));

    const dialog = document.getElementById('price-project-view');
    dialog?.addEventListener('close', () => {
      if (lastOpener?.isConnected) lastOpener.focus();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
