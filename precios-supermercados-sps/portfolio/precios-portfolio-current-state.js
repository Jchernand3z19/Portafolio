(() => {
  const STATE = Object.freeze({
    asOf: '2026-09-04',
    supermarkets: 6,
    locations: 11,
    products: 56769,
    history: 108315,
    chains: Object.freeze([
      Object.freeze({ name: 'La Colonia', locations: 'SPS · Tegucigalpa' }),
      Object.freeze({ name: 'Supermercados Colonial', locations: 'SPS' }),
      Object.freeze({ name: 'Walmart', locations: 'SPS · TGU FFAA · TGU El Sauce' }),
      Object.freeze({ name: 'PriceSmart', locations: 'SPS 6603 · Florencia 6602' }),
      Object.freeze({ name: 'Comisariato Los Andes', locations: 'SPS' }),
      Object.freeze({ name: 'Paiz', locations: 'TGU Multiplaza · TGU Próceres' })
    ])
  });

  const copy = {
    es: {
      cardLabels: ['supermercados', 'ubicaciones', 'productos registrados', 'registros históricos'],
      stage: '6 supermercados integrados, 11 ubicaciones, 56K+ productos registrados y 108K+ periodos históricos de precio.',
      scaleTitle: 'Cobertura productiva actual',
      scaleBody: 'Estado verificado al 4 de septiembre de 2026. La cobertura productiva incluye las seis cadenas que ya tienen datos aceptados en la base.',
      scaleLabels: ['supermercados', 'ubicaciones monitoreadas', 'productos registrados', 'registros históricos de precio'],
      coverageTitle: 'Supermercados con datos disponibles',
      coverageBody: 'Cada fila corresponde a una cadena con datos productivos aceptados. La cobertura de scraping y la cobertura de comparación cross-source se muestran como conceptos separados.',
      chain: 'Supermercado',
      locations: 'Ubicaciones con datos',
      status: 'Estado',
      accepted: 'Datos aceptados',
      sampleTitle: 'Comparaciones cross-source con identidad fuerte',
      sampleBody: 'La muestra anterior se retiró porque marca + presentación no demuestran que dos registros sean el mismo producto. El comparador ahora exige identidad fuerte y consistencia comercial antes de calcular un mejor precio.',
      sampleNote: 'El dataset público se vuelve a habilitar únicamente con filas que superen el gate fail-closed. Passion Jaguar y Passion Especial quedan bloqueados como comparación automática aunque compartan marca y presentación.',
      roadmap: 'Seis cadenas productivas integradas bajo una estructura común.'
    },
    en: {
      cardLabels: ['retail chains', 'locations', 'products recorded', 'historical records'],
      stage: '6 integrated retail chains, 11 locations, 56K+ products recorded, and 108K+ historical price periods.',
      scaleTitle: 'Current production coverage',
      scaleBody: 'Verified state as of September 4, 2026. Production coverage includes all six chains with accepted data in the database.',
      scaleLabels: ['retail chains', 'monitored locations', 'products recorded', 'historical price records'],
      coverageTitle: 'Retail chains with available data',
      coverageBody: 'Each row is a chain with accepted production data. Scraping coverage and cross-source comparison coverage are shown as separate concepts.',
      chain: 'Retail chain',
      locations: 'Locations with data',
      status: 'Status',
      accepted: 'Accepted data',
      sampleTitle: 'Cross-source comparisons with strong identity',
      sampleBody: 'The previous sample was removed because brand + presentation do not prove that two records are the same commercial product. The comparator now requires strong identity and commercial consistency before calculating a best price.',
      sampleNote: 'The public comparison dataset is enabled only for rows that pass the fail-closed gate. Passion Jaguar and Passion Especial remain blocked from automatic comparison even when brand and presentation match.',
      roadmap: 'Six production retail chains integrated under one shared structure.'
    }
  };

  function locale() {
    return window.PortfolioI18n?.getLocale?.() === 'en' ? 'en' : 'es';
  }

  function text() {
    return copy[locale()];
  }

  function setText(node, value) {
    if (node) node.textContent = value;
  }

  function patchCard() {
    const card = document.querySelector('#proyectos .price-card');
    if (!card) return;
    const values = ['6', '11', '56K+', '108K+'];
    card.querySelectorAll('.price-card__signal > span').forEach((item, index) => {
      setText(item.querySelector('strong'), values[index]);
      setText(item.querySelector('small'), text().cardLabels[index]);
    });
  }

  function coverageMarkup() {
    const c = text();
    const rows = STATE.chains.map(chain => `
      <tr>
        <td>${chain.name}</td>
        <td>${chain.locations}</td>
        <td><span class="price-coverage-status">${c.accepted}</span></td>
      </tr>`).join('');

    return `
      <div class="price-coverage-block" data-price-coverage>
        <div class="price-coverage__head">
          <h4>${c.coverageTitle}</h4>
          <p>${c.coverageBody}</p>
        </div>
        <div class="price-coverage-wrap" tabindex="0" aria-label="${c.coverageTitle}">
          <table class="price-coverage-table">
            <thead>
              <tr>
                <th>${c.chain}</th>
                <th>${c.locations}</th>
                <th>${c.status}</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }

  function disableLegacyCrossSourceSample(detail) {
    const c = text();
    const sampleTitle = detail.querySelector('#price-sample-title');
    setText(sampleTitle, c.sampleTitle);
    const sampleSection = sampleTitle?.closest('.price-section');
    const sampleHead = sampleTitle?.closest('.price-section__head');
    setText(sampleHead?.querySelector('p:not(.price-eyebrow)'), c.sampleBody);

    const tableWrap = sampleSection?.querySelector('.price-table-wrap');
    if (tableWrap) {
      tableWrap.hidden = true;
      tableWrap.setAttribute('aria-hidden', 'true');
    }
    sampleSection?.querySelector('[data-price-ranking-legend]')?.remove();
    const note = sampleSection?.querySelector('.price-note');
    setText(note, c.sampleNote);
    if (note) note.dataset.comparisonSafety = 'fail-closed';
  }

  function patchDetail() {
    const detail = document.querySelector('#price-project-view');
    if (!detail) return;

    const c = text();
    setText(detail.querySelector('.price-stage span'), c.stage);

    const scaleTitle = detail.querySelector('#price-scale-title');
    setText(scaleTitle, c.scaleTitle);
    const scaleHead = scaleTitle?.closest('.price-section__head');
    setText(scaleHead?.querySelector('p:not(.price-eyebrow)'), c.scaleBody);

    const values = ['6', '11', '56K+', '108K+'];
    detail.querySelectorAll('.price-kpis .price-kpi').forEach((item, index) => {
      setText(item.querySelector('strong'), values[index]);
      setText(item.querySelector('span'), c.scaleLabels[index]);
    });

    const scaleSection = scaleTitle?.closest('.price-section');
    scaleSection?.querySelector('[data-price-coverage]')?.remove();
    scaleSection?.insertAdjacentHTML('beforeend', coverageMarkup());

    disableLegacyCrossSourceSample(detail);

    const roadmap = detail.querySelector('.price-roadmap__item.is-done span');
    setText(roadmap, c.roadmap);
  }

  function apply() {
    patchCard();
    patchDetail();
  }

  function mount() {
    apply();
    window.PortfolioI18n?.onChange?.(apply);
    window.PricePortfolioCurrentState = STATE;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
