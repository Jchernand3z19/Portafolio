(() => {
  const PROJECT_ID = 'precios-supermercados';
  const REPO = 'https://github.com/Jchernand3z19/Portafolio/tree/main/precios-supermercados-sps';

  const VERIFIED_SAMPLE = Object.freeze({
    asOfUtc: '2026-09-04T01:44:35.172709Z',
    city: 'San Pedro Sula',
    snapshotSha256: 'a1fe77e3c3132c96c01f7cd792084d47ae25fbb09e3eb69fb67b230d5f09f9fc',
    rows: Object.freeze([
      Object.freeze({
        product: 'Rica yema huevos 15 unds',
        currentPrice: '61.85',
        regularPrice: '88.50',
        promotion: true,
        availability: 'not_confirmed'
      }),
      Object.freeze({
        product: 'Arroz progreso grano largo 5 lb',
        currentPrice: '84.50',
        regularPrice: null,
        promotion: false,
        availability: 'not_confirmed'
      }),
      Object.freeze({
        product: 'Nestle agua purificada 0.5 ltr',
        currentPrice: '8.95',
        regularPrice: null,
        promotion: false,
        availability: 'not_confirmed'
      })
    ])
  });

  const translations = {
    es: {
      'card.preview.sources': 'fuentes integradas',
      'card.preview.locations': 'ubicaciones monitoreadas',
      'card.preview.products': 'productos registrados',
      'card.preview.history': 'registros históricos',
      'card.previewLabel': 'Abrir proyecto de monitoreo de precios de supermercados',
      'card.title': 'Precios de Supermercados: monitoreo e inteligencia de precios',
      'card.body': 'Sistema que reúne precios públicos de supermercados, los valida y conserva su historial para detectar cambios, promociones y diferencias entre ciudades o tiendas.',
      'card.open': 'Explorar proyecto',
      'card.repo': 'Ver código',
      'dialog.close': 'Cerrar',
      'dialog.back': 'Volver a proyectos',
      'hero.kicker': 'Proyecto principal · datos reales',
      'hero.title': 'Monitoreo de precios de supermercados',
      'hero.question': '¿Cómo cambian los precios de productos cotidianos según la ciudad, la tienda o el momento?',
      'hero.body': 'El proyecto transforma catálogos públicos en una base organizada y verificable. El objetivo es convertir precios dispersos en información que luego pueda compararse, historizarse y analizarse.',
      'hero.stageTitle': 'Estado actual',
      'hero.stageBody': '5 fuentes integradas, 9 ubicaciones y más de 47 mil productos registrados. El histórico ya supera los 90 mil registros de precio.',
      'flow.title': 'Qué hace el sistema',
      'flow.body': 'El proceso está pensado para convertir información pública de distintos supermercados en datos claros y utilizables.',
      'flow.public.title': 'Encuentra precios públicos',
      'flow.public.body': 'Identifica catálogos y superficies públicas que realmente contienen precios útiles.',
      'flow.collect.title': 'Recolecta catálogos',
      'flow.collect.body': 'Captura los productos y precios de cada fuente aceptada.',
      'flow.validate.title': 'Revisa los datos',
      'flow.validate.body': 'Comprueba que la captura esté completa antes de aceptar cambios.',
      'flow.structure.title': 'Organiza la información',
      'flow.structure.body': 'Guarda producto, ciudad, precio, promoción y otros campos bajo una estructura común.',
      'flow.usable.title': 'Conserva el historial',
      'flow.usable.body': 'Mantiene el estado actual y los cambios de precio para análisis posteriores.',
      'scale.title': 'Cobertura actual',
      'scale.body': 'Cifras verificadas sobre la rama principal del proyecto al 4 de septiembre de 2026.',
      'scale.sources': 'fuentes integradas',
      'scale.locations': 'ubicaciones monitoreadas',
      'scale.products': 'productos registrados',
      'scale.history': 'registros históricos de precio',
      'sample.title': 'Ejemplo real de los datos',
      'sample.body': 'Esta muestra proviene de una captura real aceptada el 4 de septiembre de 2026 en San Pedro Sula. Se muestran sólo campos fáciles de entender; el dataset completo no se carga en la página.',
      'sample.product': 'Producto',
      'sample.city': 'Ciudad',
      'sample.current': 'Precio actual',
      'sample.regular': 'Precio regular',
      'sample.promo': 'Promoción',
      'sample.availability': 'Disponibilidad',
      'sample.yes': 'Sí',
      'sample.no': 'No',
      'sample.notConfirmed': 'No confirmada',
      'sample.note': 'Datos reales del último snapshot aceptado para esta muestra. Captura: 4 sep 2026. La disponibilidad se muestra como “No confirmada” cuando la fuente no permite interpretarla con seguridad.',
      'insights.title': 'Qué ya permiten ver los datos',
      'insights.body': 'Las comparaciones se hacen únicamente cuando se sabe que se está observando el mismo artículo dentro de una misma fuente. No se fuerza una comparación entre supermercados distintos.',
      'insights.one.value': '255',
      'insights.one.body': 'artículos presentaron diferencias comerciales entre dos tiendas de una misma cadena, dentro de 12,042 artículos comparables.',
      'insights.two.value': '115',
      'insights.two.body': 'artículos tuvieron distinto precio actual entre dos clubes, dentro de 5,129 productos con precio en ambos.',
      'insights.three.value': '120',
      'insights.three.body': 'promociones reales fueron verificadas en la captura más reciente de una fuente de San Pedro Sula con 6,646 productos con precio.',
      'value.title': 'Por qué este proyecto importa',
      'value.body': 'El valor no está sólo en recolectar páginas. Está en convertir miles de precios en una base que pueda responder preguntas de negocio.',
      'value.manual.title': 'Reduce trabajo manual',
      'value.manual.body': 'Centraliza información que de otra manera tendría que revisarse producto por producto y supermercado por supermercado.',
      'value.changes.title': 'Hace visibles los cambios',
      'value.changes.body': 'Permite detectar diferencias de precio, promociones y variaciones entre puntos de venta cuando la comparación es válida.',
      'value.history.title': 'Construye contexto',
      'value.history.body': 'El histórico permite pasar de “cuánto cuesta hoy” a entender cómo se ha movido un precio con el tiempo.',
      'roadmap.title': 'Qué sigue',
      'roadmap.body': 'La recolección y el histórico ya están construidos. Las siguientes etapas convierten esa base en una experiencia de comparación más completa.',
      'roadmap.01.status': 'Completado',
      'roadmap.01.title': 'Fuentes y datos',
      'roadmap.01.body': 'Cinco fuentes integradas bajo una estructura común.',
      'roadmap.02.status': 'Activo',
      'roadmap.02.title': 'Historial de precios',
      'roadmap.02.body': 'Se conservan los estados aceptados y sus cambios comerciales.',
      'roadmap.03.status': 'Activo',
      'roadmap.03.title': 'Comparación dentro de cada fuente',
      'roadmap.03.body': 'Ya existen comparaciones verificadas entre tiendas o clubes de una misma cadena.',
      'roadmap.04.status': 'Siguiente',
      'roadmap.04.title': 'Identificar el mismo producto entre cadenas',
      'roadmap.04.body': 'Resolver equivalencias confiables antes de comparar supermercados diferentes.',
      'roadmap.05.status': 'Siguiente',
      'roadmap.05.title': 'Dashboard de comparación',
      'roadmap.05.body': 'Convertir el histórico y las comparaciones en una experiencia visual para consulta.',
      'tech.title': 'Tecnología detrás del proyecto',
      'tech.body': 'La parte técnica queda al final para que primero se entienda el problema y el valor del proyecto.',
      'tech.python.title': 'Python',
      'tech.python.body': 'Recolección, limpieza, validación y preparación de datos.',
      'tech.turso.title': 'Turso / SQLite',
      'tech.turso.body': 'Almacenamiento del estado actual, histórico y ejecuciones.',
      'tech.actions.title': 'GitHub Actions',
      'tech.actions.body': 'Ejecuciones controladas y automatización del proceso.',
      'tech.tests.title': 'Pruebas automatizadas',
      'tech.tests.body': 'La suite protege reglas de datos, persistencia y seguridad antes de integrar cambios.',
      'end.repo': 'Ver implementación en GitHub'
    },
    en: {
      'card.preview.sources': 'integrated sources',
      'card.preview.locations': 'monitored locations',
      'card.preview.products': 'products recorded',
      'card.preview.history': 'historical records',
      'card.previewLabel': 'Open grocery price monitoring project',
      'card.title': 'Grocery Prices: monitoring and price intelligence',
      'card.body': 'A system that gathers public grocery prices, validates them, and keeps their history to reveal changes, promotions, and differences between cities or stores.',
      'card.open': 'Explore project',
      'card.repo': 'View code',
      'dialog.close': 'Close',
      'dialog.back': 'Back to projects',
      'hero.kicker': 'Featured project · real data',
      'hero.title': 'Grocery price monitoring',
      'hero.question': 'How do everyday product prices change by city, store, or over time?',
      'hero.body': 'The project turns public catalogs into an organized, verifiable dataset. The goal is to convert scattered prices into information that can be compared, historized, and analyzed.',
      'hero.stageTitle': 'Current status',
      'hero.stageBody': '5 integrated sources, 9 locations, and more than 47 thousand products recorded. Price history already exceeds 90 thousand records.',
      'flow.title': 'What the system does',
      'flow.body': 'The process turns public information from different retailers into clear, usable data.',
      'flow.public.title': 'Finds public prices',
      'flow.public.body': 'Identifies public catalogs and surfaces that actually contain useful pricing information.',
      'flow.collect.title': 'Collects catalogs',
      'flow.collect.body': 'Captures products and prices from each accepted source.',
      'flow.validate.title': 'Checks the data',
      'flow.validate.body': 'Confirms a capture is complete before accepting changes.',
      'flow.structure.title': 'Organizes the information',
      'flow.structure.body': 'Stores product, city, price, promotion, and other fields under one structure.',
      'flow.usable.title': 'Keeps price history',
      'flow.usable.body': 'Maintains current state and price changes for later analysis.',
      'scale.title': 'Current coverage',
      'scale.body': 'Figures verified on the project’s main branch as of September 4, 2026.',
      'scale.sources': 'integrated sources',
      'scale.locations': 'monitored locations',
      'scale.products': 'products recorded',
      'scale.history': 'historical price records',
      'sample.title': 'A real data example',
      'sample.body': 'This sample comes from a real accepted capture on September 4, 2026 in San Pedro Sula. Only easy-to-read fields are shown; the full production dataset is not loaded into the page.',
      'sample.product': 'Product',
      'sample.city': 'City',
      'sample.current': 'Current price',
      'sample.regular': 'Regular price',
      'sample.promo': 'Promotion',
      'sample.availability': 'Availability',
      'sample.yes': 'Yes',
      'sample.no': 'No',
      'sample.notConfirmed': 'Not confirmed',
      'sample.note': 'Real data from the latest accepted snapshot used for this sample. Capture: Sep 4, 2026. Availability is shown as “Not confirmed” when the source does not support a reliable interpretation.',
      'insights.title': 'What the data can already reveal',
      'insights.body': 'Comparisons are made only when the same item is known to be observed within one source. Products from different retailers are not forced into a match.',
      'insights.one.value': '255',
      'insights.one.body': 'items showed commercial differences between two stores from the same chain, among 12,042 comparable items.',
      'insights.two.value': '115',
      'insights.two.body': 'items had a different current price between two clubs, among 5,129 products priced in both.',
      'insights.three.value': '120',
      'insights.three.body': 'real promotions were verified in the latest capture from one San Pedro Sula source containing 6,646 priced products.',
      'value.title': 'Why this project matters',
      'value.body': 'The value is not simply scraping pages. It is turning thousands of prices into a dataset that can answer business questions.',
      'value.manual.title': 'Reduces manual work',
      'value.manual.body': 'Centralizes information that would otherwise need to be checked product by product and retailer by retailer.',
      'value.changes.title': 'Makes changes visible',
      'value.changes.body': 'It can expose price differences, promotions, and variations between stores when the comparison is valid.',
      'value.history.title': 'Builds context',
      'value.history.body': 'Price history moves the question beyond “what does it cost today?” toward understanding how a price changes over time.',
      'roadmap.title': 'What comes next',
      'roadmap.body': 'Collection and history are already built. The next stages turn that foundation into a richer comparison experience.',
      'roadmap.01.status': 'Completed',
      'roadmap.01.title': 'Sources and data',
      'roadmap.01.body': 'Five sources integrated under one shared structure.',
      'roadmap.02.status': 'Active',
      'roadmap.02.title': 'Price history',
      'roadmap.02.body': 'Accepted commercial states and their changes are preserved.',
      'roadmap.03.status': 'Active',
      'roadmap.03.title': 'Comparison within each source',
      'roadmap.03.body': 'Verified comparisons already exist between stores or clubs from the same chain.',
      'roadmap.04.status': 'Next',
      'roadmap.04.title': 'Identify the same product across chains',
      'roadmap.04.body': 'Resolve reliable equivalence before comparing different retailers.',
      'roadmap.05.status': 'Next',
      'roadmap.05.title': 'Comparison dashboard',
      'roadmap.05.body': 'Turn the history and comparisons into a visual exploration experience.',
      'tech.title': 'Technology behind the project',
      'tech.body': 'Technical details come last so the problem and business value are clear first.',
      'tech.python.title': 'Python',
      'tech.python.body': 'Collection, cleaning, validation, and data preparation.',
      'tech.turso.title': 'Turso / SQLite',
      'tech.turso.body': 'Storage for current state, history, and executions.',
      'tech.actions.title': 'GitHub Actions',
      'tech.actions.body': 'Controlled executions and process automation.',
      'tech.tests.title': 'Automated tests',
      'tech.tests.body': 'The suite protects data, persistence, and security rules before changes are integrated.',
      'end.repo': 'View implementation on GitHub'
    }
  };

  function i18n() {
    return window.PortfolioI18n;
  }

  function t(key) {
    return i18n()?.t(`prices.${key}`) ?? translations.es[key] ?? key;
  }

  function registerTranslations() {
    const api = i18n();
    if (!api) throw new Error('El módulo de precios requiere PortfolioI18n.');
    api.registerCatalog('prices', translations);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function money(value) {
    return value == null ? '—' : `L ${value}`;
  }

  function card() {
    return `
      <article class="card project-card price-card fade-in is-visible">
        <button class="price-card__preview" data-price-open type="button" aria-label="${t('card.previewLabel')}">
          <span class="price-card__signal" aria-hidden="true">
            <span><strong>5</strong><small>${t('card.preview.sources')}</small></span>
            <span><strong>9</strong><small>${t('card.preview.locations')}</small></span>
            <span><strong>47K+</strong><small>${t('card.preview.products')}</small></span>
            <span><strong>90K+</strong><small>${t('card.preview.history')}</small></span>
          </span>
        </button>
        <div class="price-card__content">
          <div class="tags">
            <span class="tag">Python</span>
            <span class="tag">Turso / SQLite</span>
            <span class="tag">GitHub Actions</span>
          </div>
          <h3>${t('card.title')}</h3>
          <p>${t('card.body')}</p>
          <div class="price-card__actions">
            <button class="text-link" data-price-open type="button">${t('card.open')}</button>
            <a class="text-link text-link--muted" href="${REPO}" target="_blank" rel="noopener noreferrer">${t('card.repo')}</a>
          </div>
        </div>
      </article>`;
  }

  function sampleRows() {
    return VERIFIED_SAMPLE.rows.map(row => `
      <tr>
        <td>${escapeHtml(row.product)}</td>
        <td>${escapeHtml(VERIFIED_SAMPLE.city)}</td>
        <td>${money(row.currentPrice)}</td>
        <td>${money(row.regularPrice)}</td>
        <td>${row.promotion ? t('sample.yes') : t('sample.no')}</td>
        <td>${t('sample.notConfirmed')}</td>
      </tr>`).join('');
  }

  function view() {
    return `
      <dialog class="price-view" id="price-project-view" aria-labelledby="price-title">
        <div class="price-view__top">
          <span class="price-view__brand">JC HERNANDEZ</span>
          <button class="price-close" data-price-close type="button">${t('dialog.close')}</button>
        </div>
        <div class="price-view__body">
          <header class="price-hero">
            <div>
              <p class="price-kicker">${t('hero.kicker')}</p>
              <h2 id="price-title">${t('hero.title')}</h2>
              <p class="price-hero__question">${t('hero.question')}</p>
              <p>${t('hero.body')}</p>
            </div>
            <aside class="price-stage" aria-label="${t('hero.stageTitle')}">
              <strong>${t('hero.stageTitle')}</strong>
              <span>${t('hero.stageBody')}</span>
            </aside>
          </header>

          <section class="price-section" aria-labelledby="price-flow-title">
            <div class="price-section__head">
              <p class="price-eyebrow">01</p>
              <h3 id="price-flow-title">${t('flow.title')}</h3>
              <p>${t('flow.body')}</p>
            </div>
            <div class="price-flow">
              <article class="price-flow__step"><strong>${t('flow.public.title')}</strong><span>${t('flow.public.body')}</span></article>
              <article class="price-flow__step"><strong>${t('flow.collect.title')}</strong><span>${t('flow.collect.body')}</span></article>
              <article class="price-flow__step"><strong>${t('flow.validate.title')}</strong><span>${t('flow.validate.body')}</span></article>
              <article class="price-flow__step"><strong>${t('flow.structure.title')}</strong><span>${t('flow.structure.body')}</span></article>
              <article class="price-flow__step"><strong>${t('flow.usable.title')}</strong><span>${t('flow.usable.body')}</span></article>
            </div>
          </section>

          <section class="price-section" aria-labelledby="price-scale-title">
            <div class="price-section__head">
              <p class="price-eyebrow">02</p>
              <h3 id="price-scale-title">${t('scale.title')}</h3>
              <p>${t('scale.body')}</p>
            </div>
            <div class="price-kpis">
              <div class="price-kpi"><strong>5</strong><span>${t('scale.sources')}</span></div>
              <div class="price-kpi"><strong>9</strong><span>${t('scale.locations')}</span></div>
              <div class="price-kpi"><strong>47K+</strong><span>${t('scale.products')}</span></div>
              <div class="price-kpi"><strong>90K+</strong><span>${t('scale.history')}</span></div>
            </div>
          </section>

          <section class="price-section" aria-labelledby="price-sample-title">
            <div class="price-section__head">
              <p class="price-eyebrow">03</p>
              <h3 id="price-sample-title">${t('sample.title')}</h3>
              <p>${t('sample.body')}</p>
            </div>
            <div class="price-table-wrap" tabindex="0" aria-label="${t('sample.title')}">
              <table class="price-table">
                <thead><tr>
                  <th>${t('sample.product')}</th>
                  <th>${t('sample.city')}</th>
                  <th>${t('sample.current')}</th>
                  <th>${t('sample.regular')}</th>
                  <th>${t('sample.promo')}</th>
                  <th>${t('sample.availability')}</th>
                </tr></thead>
                <tbody>${sampleRows()}</tbody>
              </table>
            </div>
            <p class="price-note">${t('sample.note')}</p>
          </section>

          <section class="price-section" aria-labelledby="price-insights-title">
            <div class="price-section__head">
              <p class="price-eyebrow">04</p>
              <h3 id="price-insights-title">${t('insights.title')}</h3>
              <p>${t('insights.body')}</p>
            </div>
            <div class="price-insights">
              <article class="price-insight"><strong>${t('insights.one.value')}</strong><p>${t('insights.one.body')}</p></article>
              <article class="price-insight"><strong>${t('insights.two.value')}</strong><p>${t('insights.two.body')}</p></article>
              <article class="price-insight"><strong>${t('insights.three.value')}</strong><p>${t('insights.three.body')}</p></article>
            </div>
          </section>

          <section class="price-section" aria-labelledby="price-value-title">
            <div class="price-section__head">
              <p class="price-eyebrow">05</p>
              <h3 id="price-value-title">${t('value.title')}</h3>
              <p>${t('value.body')}</p>
            </div>
            <div class="price-value-grid">
              <article class="price-value"><h4>${t('value.manual.title')}</h4><p>${t('value.manual.body')}</p></article>
              <article class="price-value"><h4>${t('value.changes.title')}</h4><p>${t('value.changes.body')}</p></article>
              <article class="price-value"><h4>${t('value.history.title')}</h4><p>${t('value.history.body')}</p></article>
            </div>
          </section>

          <section class="price-section" aria-labelledby="price-roadmap-title">
            <div class="price-section__head">
              <p class="price-eyebrow">06</p>
              <h3 id="price-roadmap-title">${t('roadmap.title')}</h3>
              <p>${t('roadmap.body')}</p>
            </div>
            <div class="price-roadmap">
              <article class="price-roadmap__item is-done"><b>01 · ${t('roadmap.01.status')}</b><strong>${t('roadmap.01.title')}</strong><span>${t('roadmap.01.body')}</span></article>
              <article class="price-roadmap__item is-active"><b>02 · ${t('roadmap.02.status')}</b><strong>${t('roadmap.02.title')}</strong><span>${t('roadmap.02.body')}</span></article>
              <article class="price-roadmap__item is-active"><b>03 · ${t('roadmap.03.status')}</b><strong>${t('roadmap.03.title')}</strong><span>${t('roadmap.03.body')}</span></article>
              <article class="price-roadmap__item is-next"><b>04 · ${t('roadmap.04.status')}</b><strong>${t('roadmap.04.title')}</strong><span>${t('roadmap.04.body')}</span></article>
              <article class="price-roadmap__item is-next"><b>05 · ${t('roadmap.05.status')}</b><strong>${t('roadmap.05.title')}</strong><span>${t('roadmap.05.body')}</span></article>
            </div>
          </section>

          <section class="price-section" aria-labelledby="price-tech-title">
            <div class="price-section__head">
              <p class="price-eyebrow">07</p>
              <h3 id="price-tech-title">${t('tech.title')}</h3>
              <p>${t('tech.body')}</p>
            </div>
            <div class="price-tech">
              <article class="price-tech__item"><strong>${t('tech.python.title')}</strong><p>${t('tech.python.body')}</p></article>
              <article class="price-tech__item"><strong>${t('tech.turso.title')}</strong><p>${t('tech.turso.body')}</p></article>
              <article class="price-tech__item"><strong>${t('tech.actions.title')}</strong><p>${t('tech.actions.body')}</p></article>
              <article class="price-tech__item"><strong>${t('tech.tests.title')}</strong><p>${t('tech.tests.body')}</p></article>
            </div>
            <div class="price-end-actions">
              <button class="price-back" data-price-close type="button">${t('dialog.back')}</button>
              <a class="price-link" href="${REPO}" target="_blank" rel="noopener noreferrer">${t('end.repo')}</a>
            </div>
          </section>
        </div>
      </dialog>`;
  }

  function templateElement(markup) {
    const template = document.createElement('template');
    template.innerHTML = markup.trim();
    return template.content.firstElementChild;
  }

  function setup({ card: cardElement, detail }) {
    if (!(detail instanceof HTMLDialogElement)) {
      throw new Error('El detalle de precios debe montarse como dialog nativo.');
    }

    let opener = null;

    function open(event) {
      opener = event.currentTarget;
      if (!detail.open) detail.showModal();
      document.body.classList.add('is-locked');
      detail.scrollTop = 0;
      detail.querySelector('[data-price-close]')?.focus();
    }

    function close() {
      if (detail.open) detail.close();
    }

    function restoreAfterClose() {
      document.body.classList.remove('is-locked');
      if (opener?.isConnected) opener.focus();
    }

    cardElement.addEventListener('click', event => {
      const control = event.target.closest('[data-price-open]');
      if (control && cardElement.contains(control)) open({ currentTarget: control });
    });

    detail.addEventListener('click', event => {
      if (event.target.closest('[data-price-close]')) close();
    });
    detail.addEventListener('close', restoreAfterClose);
    detail.addEventListener('cancel', () => {
      document.body.classList.remove('is-locked');
    });

    i18n().onChange(() => {
      const wasOpen = detail.open;
      const freshCard = templateElement(card());
      const freshDetail = templateElement(view());
      cardElement.innerHTML = freshCard.innerHTML;
      detail.innerHTML = freshDetail.innerHTML;
      if (wasOpen) {
        opener = cardElement.querySelector('[data-price-open]');
        detail.querySelector('[data-price-close]')?.focus();
      }
    });
  }

  function mount() {
    if (!window.PortfolioProjects || !i18n()) {
      console.error('No se encontraron las dependencias del proyecto Precios de Supermercados.');
      return;
    }

    registerTranslations();
    window.PortfolioProjects.register({
      id: PROJECT_ID,
      cardHtml: card(),
      detailHtml: view(),
      setup
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
