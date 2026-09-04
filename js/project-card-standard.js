(() => {
  const COPY = {
    es: {
      featured: 'PROYECTO PRINCIPAL · 01',
      standard: 'PROYECTO · 02',
      priceKind: 'WEB SCRAPING · DATOS REALES',
      worldCupKind: 'ANÁLISIS PREDICTIVO · DASHBOARD REAL',
      explore: 'Explorar proyecto',
      result: 'Ver resultado',
      code: 'Ver código'
    },
    en: {
      featured: 'FEATURED PROJECT · 01',
      standard: 'PROJECT · 02',
      priceKind: 'WEB SCRAPING · REAL DATA',
      worldCupKind: 'PREDICTIVE ANALYSIS · LIVE DASHBOARD',
      explore: 'Explore project',
      result: 'View result',
      code: 'View code'
    }
  };

  let localeSubscriptionReady = false;

  function locale() {
    return window.PortfolioI18n?.getLocale?.() === 'en' ? 'en' : 'es';
  }

  function setText(element, value) {
    if (element && element.textContent !== value) element.textContent = value;
  }

  function decorateAction(element, role) {
    if (!element) return;
    element.classList.add('portfolio-card__action', `portfolio-card__action--${role}`);
  }

  function normalizePriceCard(copy) {
    const card = document.querySelector('#proyectos .price-card');
    if (!card) return;

    card.classList.add('project-card', 'portfolio-card-standard');
    card.dataset.projectPosition = copy.featured;

    card.querySelector('.price-card__preview')?.classList.add('portfolio-card__visual');
    card.querySelector('.price-card__content')?.classList.add('portfolio-card__body');

    const badge = card.querySelector('.price-card__badge');
    if (badge) {
      badge.classList.add('portfolio-card__kind');
      setText(badge, copy.priceKind);
    }

    card.querySelector('.tags')?.classList.add('portfolio-card__tags');

    const actions = card.querySelector('.price-card__actions');
    if (actions) {
      actions.classList.add('portfolio-card__actions');
      const controls = Array.from(actions.querySelectorAll('button, a'));
      decorateAction(controls[0], 'primary');
      decorateAction(controls[1], 'secondary');
      decorateAction(controls[2], 'tertiary');
      setText(controls[0], copy.explore);
      setText(controls[1], copy.result);
      setText(controls[2], copy.code);
    }
  }

  function normalizeWorldCupCard(copy) {
    const card = document.querySelector('#proyectos .mw-card');
    if (!card) return;

    card.classList.add('project-card', 'portfolio-card-standard');
    card.dataset.projectPosition = copy.standard;

    card.querySelector('.mw-card__media')?.classList.add('portfolio-card__visual');
    const body = card.querySelector('.mw-card__body');
    body?.classList.add('portfolio-card__body');

    if (body) {
      let badge = body.querySelector('.portfolio-card__kind');
      if (!badge) {
        badge = document.createElement('p');
        badge.className = 'portfolio-card__kind';
        body.insertBefore(badge, body.firstChild);
      }
      setText(badge, copy.worldCupKind);
    }

    card.querySelector('.mw-tags')?.classList.add('portfolio-card__tags');

    const actions = card.querySelector('.mw-actions');
    if (actions) {
      actions.classList.add('portfolio-card__actions');
      const controls = Array.from(actions.querySelectorAll('button, a'));
      decorateAction(controls[0], 'primary');
      decorateAction(controls[1], 'secondary');
      decorateAction(controls[2], 'tertiary');
      setText(controls[0], copy.explore);
      setText(controls[1], copy.result);
      setText(controls[2], copy.code);
    }
  }

  function subscribeLocale() {
    if (localeSubscriptionReady || !window.PortfolioI18n?.onChange) return;
    localeSubscriptionReady = true;
    window.PortfolioI18n.onChange(apply);
  }

  function apply() {
    const copy = COPY[locale()];
    normalizePriceCard(copy);
    normalizeWorldCupCard(copy);
    subscribeLocale();
  }

  const observer = new MutationObserver(() => apply());
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply, { once: true });
  } else {
    apply();
  }

  window.setTimeout(apply, 0);
})();