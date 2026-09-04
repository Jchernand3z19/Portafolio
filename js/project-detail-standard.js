(() => {
  const COPY = {
    es: {
      projects: 'Proyectos',
      priceMeta: 'PROYECTO PRINCIPAL · 01 · WEB SCRAPING · DATOS REALES',
      mundialMeta: 'PROYECTO · 02 · ANÁLISIS PREDICTIVO · DASHBOARD REAL',
      viewResult: 'Ver resultado',
      viewCode: 'Ver código'
    },
    en: {
      projects: 'Projects',
      priceMeta: 'FEATURED PROJECT · 01 · WEB SCRAPING · REAL DATA',
      mundialMeta: 'PROJECT · 02 · PREDICTIVE ANALYSIS · LIVE DASHBOARD',
      viewResult: 'View result',
      viewCode: 'View code'
    }
  };

  let localeSubscriptionReady = false;

  function locale() {
    return window.PortfolioI18n?.getLocale?.() === 'en' ? 'en' : 'es';
  }

  function setText(node, text) {
    if (node && node.textContent !== text) node.textContent = text;
  }

  function makeBreadcrumb({ parent, before, backButton, title }) {
    if (!parent || parent.querySelector('.portfolio-detail__breadcrumb')) return;
    const breadcrumb = document.createElement('div');
    breadcrumb.className = 'portfolio-detail__breadcrumb';
    const back = document.createElement('button');
    back.type = 'button';
    back.dataset.projectDetailBack = 'true';
    back.textContent = COPY[locale()].projects;
    back.addEventListener('click', () => backButton?.click());
    const separator = document.createElement('span');
    separator.textContent = '/';
    const current = document.createElement('span');
    current.dataset.projectDetailCurrent = 'true';
    current.textContent = title || '';
    breadcrumb.append(back, separator, current);
    parent.insertBefore(breadcrumb, before || parent.firstChild);
  }

  function ensureMeta(hero, text, legacyKicker) {
    if (!hero) return;
    let meta = hero.querySelector('.portfolio-detail__meta');
    if (!meta) {
      meta = document.createElement('p');
      meta.className = 'portfolio-detail__meta';
      const target = hero.querySelector('h2')?.parentElement || hero.firstElementChild || hero;
      target.insertBefore(meta, target.firstChild);
    }
    setText(meta, text);
    legacyKicker?.remove();
  }

  function normalizePrice(copy) {
    const view = document.getElementById('price-project-view');
    if (!view) return;
    view.classList.add('portfolio-detail-standard');

    const body = view.querySelector('.price-view__body');
    const hero = view.querySelector('.price-hero');
    const title = view.querySelector('#price-title');
    const close = view.querySelector('[data-price-close]');
    const back = view.querySelector('[data-price-back]') || close;

    makeBreadcrumb({ parent: body, before: hero, backButton: back, title: title?.textContent });
    ensureMeta(hero, copy.priceMeta, hero?.querySelector('.price-kicker'));

    const breadcrumb = body?.querySelector('.portfolio-detail__breadcrumb');
    setText(breadcrumb?.querySelector('[data-project-detail-back]'), copy.projects);
    setText(breadcrumb?.querySelector('[data-project-detail-current]'), title?.textContent || '');

    let actions = hero?.querySelector('.portfolio-detail__actions');
    if (!actions && hero) {
      actions = document.createElement('div');
      actions.className = 'portfolio-detail__actions';
      const mainColumn = hero.firstElementChild || hero;

      const result = document.createElement('button');
      result.type = 'button';
      result.className = 'portfolio-detail__action portfolio-detail__action--primary';
      result.dataset.projectDetailResult = 'price';
      result.textContent = copy.viewResult;
      result.addEventListener('click', () => {
        view.querySelector('#price-sample-title')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });

      const sourceCode = document.querySelector('#proyectos .price-card .portfolio-card__action--tertiary')
        || document.querySelector('#proyectos .price-card .price-card__actions a:last-child');
      const code = document.createElement('a');
      code.className = 'portfolio-detail__action portfolio-detail__action--secondary';
      code.dataset.projectDetailCode = 'price';
      code.href = sourceCode?.href || 'https://github.com/Jchernand3z19/Portafolio/tree/main/precios-supermercados-sps';
      code.target = '_blank';
      code.rel = 'noopener';
      code.textContent = copy.viewCode;

      actions.append(result, code);
      mainColumn.appendChild(actions);
    }

    setText(actions?.querySelector('[data-project-detail-result="price"]'), copy.viewResult);
    setText(actions?.querySelector('[data-project-detail-code="price"]'), copy.viewCode);
  }

  function normalizeMundial(copy) {
    const view = document.getElementById('mw-view');
    if (!view) return;
    view.classList.add('portfolio-detail-standard');

    const shell = view.querySelector('.mw-shell');
    const breadcrumb = view.querySelector('.mw-breadcrumb');
    const hero = view.querySelector('.mw-hero');
    const title = view.querySelector('#mw-title');

    if (breadcrumb) {
      breadcrumb.classList.add('portfolio-detail__breadcrumb');
      setText(breadcrumb.querySelector('button'), copy.projects);
      const spans = breadcrumb.querySelectorAll('span');
      if (spans.length) setText(spans[spans.length - 1], title?.textContent || '');
    } else {
      makeBreadcrumb({
        parent: shell,
        before: hero,
        backButton: view.querySelector('#mw-back-top') || view.querySelector('#mw-close'),
        title: title?.textContent
      });
    }

    ensureMeta(hero, copy.mundialMeta, hero?.querySelector('.mw-kicker'));

    const actions = view.querySelector('.mw-hero__actions');
    actions?.classList.add('portfolio-detail__aside');
    const controls = actions ? Array.from(actions.querySelectorAll('a, button')) : [];
    controls.forEach((control, index) => {
      control.classList.add('portfolio-detail__action');
      control.classList.add(index === 0 ? 'portfolio-detail__action--primary' : 'portfolio-detail__action--secondary');
    });
    setText(controls[0], copy.viewResult);
    setText(controls[1], copy.viewCode);
  }

  function apply() {
    const copy = COPY[locale()];
    normalizePrice(copy);
    normalizeMundial(copy);
    if (!localeSubscriptionReady && window.PortfolioI18n?.onChange) {
      localeSubscriptionReady = true;
      window.PortfolioI18n.onChange(apply);
    }
  }

  const observer = new MutationObserver(() => apply());
  observer.observe(document.body, { childList: true, subtree: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply, { once: true });
  } else {
    apply();
  }

  window.setTimeout(apply, 0);
})();
