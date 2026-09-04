(() => {
  const PROJECT_ID = 'precios-supermercados';
  const REPO = 'https://github.com/Jchernand3z19/Portafolio/tree/main/precios-supermercados-sps';

  const translations = {
    es: {
      'card.preview.sources': 'fuentes integradas',
      'card.preview.locations': 'ubicaciones',
      'card.preview.products': 'identidades de producto',
      'card.preview.cities': 'ciudades',
      'card.previewLabel': 'Abrir proyecto Precios de Supermercados',
      'card.title': 'Precios de Supermercados: base para inteligencia de precios',
      'card.body': 'Construcción de una fuente de datos confiable a partir de precios públicos: recolección, validación, contexto por ubicación e histórico estructurado.',
      'card.open': 'Ver proyecto completo',
      'card.repo': 'Ver implementación',
      'dialog.close': 'Cerrar',
      'dialog.back': 'Volver a proyectos',
      'hero.kicker': 'Proyecto de datos · etapa actual',
      'hero.title': 'De precios dispersos a información útil',
      'hero.question': '¿Cuánto puede cambiar el precio de un producto dependiendo de la ubicación o del momento?',
      'hero.body': 'Para responderlo, primero hay que convertir información pública dispersa en datos estructurados, consistentes y trazables. Esa es la base que ya está construida.',
      'hero.stageTitle': 'Hoy',
      'hero.stageBody': 'Recolección, validación, estructuración e histórico por ubicación. La visualización analítica completa todavía no forma parte del MVP actual.',
      'flow.title': 'Qué hace hoy',
      'flow.body': 'El sistema transforma fuentes con estructuras diferentes en estados comerciales comparables dentro de cada fuente y ubicación aceptada.',
      'flow.public.title': 'Fuentes públicas',
      'flow.public.body': 'Catálogos y superficies read-only evaluadas antes de integrarse.',
      'flow.collect.title': 'Recolección',
      'flow.collect.body': 'Capturas completas con límites y evidencia reproducible.',
      'flow.validate.title': 'Validación',
      'flow.validate.body': 'Completitud, identidad, precios y consistencia antes de persistir.',
      'flow.structure.title': 'Estructuración',
      'flow.structure.body': 'Producto, ubicación y estado comercial bajo un modelo común.',
      'flow.usable.title': 'Datos utilizables',
      'flow.usable.body': 'Estado actual e histórico listos para análisis posterior.',
      'scale.title': 'Escala actual',
      'scale.body': 'Cobertura verificada en la rama principal del proyecto. Las cifras se muestran redondeadas para comunicar escala sin falsa precisión.',
      'scale.sources': 'fuentes integradas',
      'scale.locations': 'contextos de ubicación',
      'scale.products': 'identidades de producto',
      'scale.history': 'periodos históricos',
      'sample.title': 'Cómo se ve el resultado',
      'sample.body': 'El navegador no carga el dataset productivo. Esta muestra sintética reproduce únicamente la forma de los campos para explicar el resultado.',
      'sample.product': 'Producto',
      'sample.city': 'Ciudad',
      'sample.location': 'Ubicación',
      'sample.current': 'Precio actual',
      'sample.regular': 'Precio regular',
      'sample.promo': 'Promoción',
      'sample.availability': 'Disponibilidad',
      'sample.yes': 'Sí',
      'sample.no': 'No',
      'sample.unknown': 'Desconocida',
      'sample.inStock': 'Disponible',
      'sample.note': 'Muestra sintética de presentación. No corresponde a registros productivos ni identifica cadenas comerciales.',
      'insights.title': 'Hallazgos que los datos ya permiten demostrar',
      'insights.body': 'Las comparaciones se limitan a contextos de una misma fuente cuando la identidad del SKU está demostrada. No se asume equivalencia entre cadenas diferentes.',
      'insights.one.value': '255',
      'insights.one.body': 'diferencias comerciales entre dos ubicaciones de una misma fuente, sobre 12,042 SKU comparables.',
      'insights.two.value': '115',
      'insights.two.body': 'SKU con diferencia de precio actual entre dos clubes de otra fuente, sobre 5,129 con precio en ambos.',
      'insights.three.value': '120',
      'insights.three.body': 'promociones verificadas en una fuente SPS con 6,646 productos con precio; su disponibilidad se conserva como desconocida por falta de semántica fiable.',
      'quality.title': 'Calidad antes que cobertura',
      'quality.body': 'No toda fuente encontrada se incorpora. Dos cadenas candidatas fueron descartadas temporalmente para seguimiento de precios porque la superficie pública evaluada no demostró precios estructurados con suficiente calidad y trazabilidad.',
      'quality.number': '2',
      'quality.label': 'candidatas no aceptadas',
      'challenge.title': 'El desafío no es sólo extraer un precio',
      'challenge.body': 'La dificultad está en construir una fuente consistente cuando cada origen expresa ubicación, precio, promoción, disponibilidad y completitud de forma distinta.',
      'challenge.structure.title': 'Estructuras distintas',
      'challenge.structure.body': 'Las fuentes no comparten el mismo contrato, paginación ni forma de identificar producto y ubicación.',
      'challenge.commercial.title': 'Estado comercial',
      'challenge.commercial.body': 'Precio actual, precio regular, promoción y disponibilidad se validan sin rellenar campos que la fuente no demuestra.',
      'challenge.integrity.title': 'Integridad e histórico',
      'challenge.integrity.body': 'Un snapshot incompleto no modifica el estado aceptado; un replay exacto no duplica historia y un cambio real abre un nuevo periodo.',
      'roadmap.title': 'Evolución del proyecto',
      'roadmap.body': 'La base ya genera valor por sí misma y habilita capas posteriores sin presentarlas como terminadas.',
      'roadmap.01.status': 'Completado',
      'roadmap.01.title': 'Recolección y estructura',
      'roadmap.01.body': 'Cinco fuentes integradas bajo un modelo común.',
      'roadmap.02.status': 'En desarrollo',
      'roadmap.02.title': 'Histórico',
      'roadmap.02.body': 'Modelo de periodos activo; recurrencia sólo donde existe autorización operativa.',
      'roadmap.03.status': 'En desarrollo',
      'roadmap.03.title': 'Comparación por ubicación',
      'roadmap.03.body': 'Validada dentro de fuentes con identidad y contexto demostrados.',
      'roadmap.04.status': 'Próximo',
      'roadmap.04.title': 'Matching entre fuentes',
      'roadmap.04.body': 'Resolver identidad de productos antes de comparar cadenas diferentes.',
      'roadmap.05.status': 'Próximo',
      'roadmap.05.title': 'Análisis y visualización',
      'roadmap.05.body': 'Convertir el histórico validado en una experiencia analítica.',
      'future.title': 'La base para algo mayor',
      'future.today': 'HOY',
      'future.todayBody': 'Fuentes públicas → datos validados → histórico estructurado',
      'future.next': 'SIGUIENTE',
      'future.nextBody': 'Identidad entre fuentes → comparación → análisis → visualización → inteligencia de precios',
      'tech.title': 'Cómo está construido',
      'tech.body': 'La sección técnica refleja herramientas que ya participan en el sistema actual; no incluye tecnología planeada como si estuviera operativa.',
      'tech.python.title': 'Python',
      'tech.python.body': 'Captura, normalización, validación y persistencia.',
      'tech.turso.title': 'Turso / SQLite',
      'tech.turso.body': 'Cinco tablas para fuentes, ubicaciones, productos, histórico y ejecuciones.',
      'tech.actions.title': 'GitHub Actions',
      'tech.actions.body': 'Ejecuciones controladas, evidencia y automatización autorizada.',
      'tech.http.title': 'HTTP read-only',
      'tech.http.body': 'Integraciones públicas con límites, validación y comportamiento fail-closed.',
      'tech.tests.title': 'Pytest',
      'tech.tests.body': 'Más de 2,000 pruebas en el cierre más reciente integrado antes de esta presentación.',
      'end.repo': 'Ver implementación en GitHub'
    },
    en: {
      'card.preview.sources': 'integrated sources',
      'card.preview.locations': 'location contexts',
      'card.preview.products': 'product identities',
      'card.preview.cities': 'cities',
      'card.previewLabel': 'Open Grocery Price Data project',
      'card.title': 'Grocery Price Data: building a foundation for price intelligence',
      'card.body': 'Building a reliable dataset from public pricing sources through collection, validation, location context, and structured history.',
      'card.open': 'View full project',
      'card.repo': 'View implementation',
      'dialog.close': 'Close',
      'dialog.back': 'Back to projects',
      'hero.kicker': 'Data project · current stage',
      'hero.title': 'From scattered prices to useful information',
      'hero.question': 'How much can a product price change depending on location or time?',
      'hero.body': 'Answering that question starts with turning scattered public information into structured, consistent, traceable data. That foundation is already in place.',
      'hero.stageTitle': 'Today',
      'hero.stageBody': 'Collection, validation, structuring, and location-level history. A complete analytics and visualization layer is not part of the current MVP yet.',
      'flow.title': 'What it does today',
      'flow.body': 'The system turns sources with different structures into commercial states that can be compared within each accepted source and location.',
      'flow.public.title': 'Public sources',
      'flow.public.body': 'Read-only catalogs and surfaces are evaluated before integration.',
      'flow.collect.title': 'Collection',
      'flow.collect.body': 'Complete captures with bounded requests and reproducible evidence.',
      'flow.validate.title': 'Validation',
      'flow.validate.body': 'Completeness, identity, pricing, and consistency checks before persistence.',
      'flow.structure.title': 'Structuring',
      'flow.structure.body': 'Product, location, and commercial state mapped into one model.',
      'flow.usable.title': 'Usable data',
      'flow.usable.body': 'Current state and history ready for downstream analysis.',
      'scale.title': 'Current scale',
      'scale.body': 'Coverage verified on the project’s main branch. Figures are rounded to communicate scale without implying false precision.',
      'scale.sources': 'integrated sources',
      'scale.locations': 'location contexts',
      'scale.products': 'product identities',
      'scale.history': 'historical periods',
      'sample.title': 'What the output looks like',
      'sample.body': 'The browser never loads the production dataset. This synthetic sample mirrors only the field structure needed to explain the output.',
      'sample.product': 'Product',
      'sample.city': 'City',
      'sample.location': 'Location',
      'sample.current': 'Current price',
      'sample.regular': 'Regular price',
      'sample.promo': 'Promotion',
      'sample.availability': 'Availability',
      'sample.yes': 'Yes',
      'sample.no': 'No',
      'sample.unknown': 'Unknown',
      'sample.inStock': 'Available',
      'sample.note': 'Synthetic presentation sample. It is not a production record and does not identify any retailer.',
      'insights.title': 'What the data can already demonstrate',
      'insights.body': 'Comparisons are limited to contexts within the same source when SKU identity is established. Products from different retailers are not assumed to be equivalent.',
      'insights.one.value': '255',
      'insights.one.body': 'commercial differences between two locations from the same source, across 12,042 comparable SKUs.',
      'insights.two.value': '115',
      'insights.two.body': 'SKUs with a current-price difference between two clubs from another source, among 5,129 priced in both.',
      'insights.three.value': '120',
      'insights.three.body': 'verified promotions in one San Pedro Sula source with 6,646 priced products; availability remains unknown because its meaning was not demonstrated reliably.',
      'quality.title': 'Quality before coverage',
      'quality.body': 'Not every discovered source is integrated. Two candidate chains were temporarily rejected for price tracking because the evaluated public surface did not demonstrate structured prices with sufficient quality and traceability.',
      'quality.number': '2',
      'quality.label': 'candidates not accepted',
      'challenge.title': 'The hard part is not simply extracting a price',
      'challenge.body': 'The challenge is building a consistent source when each origin expresses location, price, promotion, availability, and completeness differently.',
      'challenge.structure.title': 'Different structures',
      'challenge.structure.body': 'Sources do not share the same contract, pagination, or way of identifying products and locations.',
      'challenge.commercial.title': 'Commercial state',
      'challenge.commercial.body': 'Current price, regular price, promotion, and availability are validated without filling fields the source does not actually support.',
      'challenge.integrity.title': 'Integrity and history',
      'challenge.integrity.body': 'An incomplete snapshot cannot mutate accepted state; an exact replay does not duplicate history, and a real change opens a new period.',
      'roadmap.title': 'Project evolution',
      'roadmap.body': 'The foundation already provides value while enabling future layers without presenting them as finished features.',
      'roadmap.01.status': 'Completed',
      'roadmap.01.title': 'Collection and structure',
      'roadmap.01.body': 'Five integrated sources under a shared model.',
      'roadmap.02.status': 'In development',
      'roadmap.02.title': 'History',
      'roadmap.02.body': 'Period-based history is active; recurrence exists only where operational authorization is in place.',
      'roadmap.03.status': 'In development',
      'roadmap.03.title': 'Location comparison',
      'roadmap.03.body': 'Validated within sources where identity and location context are demonstrated.',
      'roadmap.04.status': 'Next',
      'roadmap.04.title': 'Cross-source matching',
      'roadmap.04.body': 'Resolve product identity before comparing different retailers.',
      'roadmap.05.status': 'Next',
      'roadmap.05.title': 'Analysis and visualization',
      'roadmap.05.body': 'Turn validated history into an analytical experience.',
      'future.title': 'A foundation for something larger',
      'future.today': 'TODAY',
      'future.todayBody': 'Public sources → validated data → structured history',
      'future.next': 'NEXT',
      'future.nextBody': 'Cross-source identity → comparison → analysis → visualization → price intelligence',
      'tech.title': 'How it is built',
      'tech.body': 'This section lists technology already used by the current system; planned tools are not presented as operational.',
      'tech.python.title': 'Python',
      'tech.python.body': 'Collection, normalization, validation, and persistence.',
      'tech.turso.title': 'Turso / SQLite',
      'tech.turso.body': 'Five tables for sources, locations, products, price history, and runs.',
      'tech.actions.title': 'GitHub Actions',
      'tech.actions.body': 'Controlled execution, evidence, and authorized automation.',
      'tech.http.title': 'Read-only HTTP',
      'tech.http.body': 'Public integrations with bounded requests, validation, and fail-closed behavior.',
      'tech.tests.title': 'Pytest',
      'tech.tests.body': 'More than 2,000 tests passed in the latest integrated project closeout before this portfolio presentation.',
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

  function card() {
    return `
      <article class="card project-card price-card fade-in is-visible">
        <button class="price-card__preview" data-price-open type="button" aria-label="${t('card.previewLabel')}">
          <span class="price-card__signal" aria-hidden="true">
            <span><strong>5</strong><small>${t('card.preview.sources')}</small></span>
            <span><strong>9</strong><small>${t('card.preview.locations')}</small></span>
            <span><strong>47K+</strong><small>${t('card.preview.products')}</small></span>
            <span><strong>2</strong><small>${t('card.preview.cities')}</small></span>
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
    return `
      <tr><td>SKU-DEMO-01</td><td>San Pedro Sula</td><td>Contexto 01</td><td>L 84.50</td><td>L 89.00</td><td>${t('sample.yes')}</td><td>${t('sample.inStock')}</td></tr>
      <tr><td>SKU-DEMO-02</td><td>Tegucigalpa</td><td>Contexto 02</td><td>L 126.00</td><td>—</td><td>${t('sample.no')}</td><td>${t('sample.unknown')}</td></tr>
      <tr><td>SKU-DEMO-03</td><td>Tegucigalpa</td><td>Contexto 03</td><td>L 51.75</td><td>L 51.75</td><td>${t('sample.no')}</td><td>${t('sample.inStock')}</td></tr>`;
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
                  <th>${t('sample.location')}</th>
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

          <section class="price-section" aria-labelledby="price-quality-title">
            <div class="price-section__head">
              <p class="price-eyebrow">05</p>
              <h3 id="price-quality-title">${t('quality.title')}</h3>
            </div>
            <div class="price-quality">
              <div class="price-quality__number" aria-hidden="true">${t('quality.number')}</div>
              <div><strong>${t('quality.label')}</strong><p>${t('quality.body')}</p></div>
            </div>
          </section>

          <section class="price-section" aria-labelledby="price-challenge-title">
            <div class="price-section__head">
              <p class="price-eyebrow">06</p>
              <h3 id="price-challenge-title">${t('challenge.title')}</h3>
              <p>${t('challenge.body')}</p>
            </div>
            <div class="price-challenges">
              <article class="price-challenge"><h4>${t('challenge.structure.title')}</h4><p>${t('challenge.structure.body')}</p></article>
              <article class="price-challenge"><h4>${t('challenge.commercial.title')}</h4><p>${t('challenge.commercial.body')}</p></article>
              <article class="price-challenge"><h4>${t('challenge.integrity.title')}</h4><p>${t('challenge.integrity.body')}</p></article>
            </div>
          </section>

          <section class="price-section" aria-labelledby="price-roadmap-title">
            <div class="price-section__head">
              <p class="price-eyebrow">07</p>
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

          <section class="price-section" aria-labelledby="price-future-title">
            <div class="price-section__head">
              <p class="price-eyebrow">08</p>
              <h3 id="price-future-title">${t('future.title')}</h3>
            </div>
            <div class="price-future">
              <div><strong>${t('future.today')}</strong><span>${t('future.todayBody')}</span></div>
              <div class="price-future__arrow" aria-hidden="true">→</div>
              <div><strong>${t('future.next')}</strong><span>${t('future.nextBody')}</span></div>
            </div>
          </section>

          <section class="price-section" aria-labelledby="price-tech-title">
            <div class="price-section__head">
              <p class="price-eyebrow">09</p>
              <h3 id="price-tech-title">${t('tech.title')}</h3>
              <p>${t('tech.body')}</p>
            </div>
            <div class="price-tech">
              <article class="price-tech__item"><strong>${t('tech.python.title')}</strong><p>${t('tech.python.body')}</p></article>
              <article class="price-tech__item"><strong>${t('tech.turso.title')}</strong><p>${t('tech.turso.body')}</p></article>
              <article class="price-tech__item"><strong>${t('tech.actions.title')}</strong><p>${t('tech.actions.body')}</p></article>
              <article class="price-tech__item"><strong>${t('tech.http.title')}</strong><p>${t('tech.http.body')}</p></article>
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
