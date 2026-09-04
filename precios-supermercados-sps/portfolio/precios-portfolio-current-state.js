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
      coverageBody: 'Esta es la cobertura real del proyecto. Cada fila corresponde a una cadena con datos productivos aceptados; no se ocultan las cadenas que todavía no tienen matching de producto entre sí.',
      chain: 'Supermercado',
      locations: 'Ubicaciones con datos',
      status: 'Estado',
      accepted: 'Datos aceptados',
      sampleTitle: 'Comparación homologada: 10 productos en 2 supermercados',
      sampleBody: 'La cobertura total incluye 6 supermercados. Esta tabla compara únicamente Comisariato Los Andes y Supermercados Colonial porque esos 10 productos sí fueron homologados por marca y presentación. El precio más bajo se resalta en verde, el más alto en rojo y los valores intermedios se marcarán en amarillo cuando haya 3 o más precios comparables.',
      legendTitle: 'Lectura de precios',
      best: 'Mejor precio',
      middle: 'Precio intermedio',
      highest: 'Precio más alto',
      tie: 'Mejor precio (empate)',
      legendNote: 'El amarillo aparece cuando una fila tiene 3 o más precios comparables.',
      roadmap: 'Seis cadenas productivas integradas bajo una estructura común.'
    },
    en: {
      cardLabels: ['retail chains', 'locations', 'products recorded', 'historical records'],
      stage: '6 integrated retail chains, 11 locations, 56K+ products recorded, and 108K+ historical price periods.',
      scaleTitle: 'Current production coverage',
      scaleBody: 'Verified state as of September 4, 2026. Production coverage includes all six chains with accepted data in the database.',
      scaleLabels: ['retail chains', 'monitored locations', 'products recorded', 'historical price records'],
      coverageTitle: 'Retail chains with available data',
      coverageBody: 'This is the project’s real coverage. Every row is a chain with accepted production data; chains are not hidden just because cross-source product matching is not complete yet.',
      chain: 'Retail chain',
      locations: 'Locations with data',
      status: 'Status',
      accepted: 'Accepted data',
      sampleTitle: 'Matched comparison: 10 products across 2 retailers',
      sampleBody: 'Total coverage includes 6 retail chains. This table compares only Comisariato Los Andes and Supermercados Colonial because these 10 products were matched by brand and presentation. The lowest price is highlighted in green, the highest in red, and intermediate values will be yellow when 3 or more comparable prices are available.',
      legendTitle: 'Price guide',
      best: 'Best price',
      middle: 'Intermediate price',
      highest: 'Highest price',
      tie: 'Best price (tie)',
      legendNote: 'Yellow appears when a row contains 3 or more comparable prices.',
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

  function rankingLegendMarkup() {
    const c = text();
    return `
      <div class="price-rank-legend" data-price-ranking-legend aria-label="${c.legendTitle}">
        <strong class="price-rank-legend__label">${c.legendTitle}</strong>
        <span class="price-rank-legend__item"><i class="price-rank-dot is-best" aria-hidden="true"></i>${c.best}</span>
        <span class="price-rank-legend__item"><i class="price-rank-dot is-middle" aria-hidden="true"></i>${c.middle}</span>
        <span class="price-rank-legend__item"><i class="price-rank-dot is-highest" aria-hidden="true"></i>${c.highest}</span>
        <small>${c.legendNote}</small>
      </div>`;
  }

  function parsePrice(cell) {
    const numeric = cell.textContent.replace(/[^0-9.,-]/g, '').replaceAll(',', '');
    const value = Number(numeric);
    return Number.isFinite(value) ? value : null;
  }

  function rankComparisonPrices(detail) {
    const c = text();
    const table = detail.querySelector('.price-table');
    if (!table) return;

    const headerRow = table.querySelector('thead tr');
    const legacyBestHeader = headerRow?.lastElementChild;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const hasLegacyBestColumn = Boolean(
      legacyBestHeader &&
      rows.length &&
      rows.every(row => row.lastElementChild?.classList.contains('price-best'))
    );

    if (hasLegacyBestColumn) {
      legacyBestHeader.classList.add('price-best-legacy');
      legacyBestHeader.setAttribute('aria-hidden', 'true');
      rows.forEach(row => {
        row.lastElementChild.classList.add('price-best-legacy');
        row.lastElementChild.setAttribute('aria-hidden', 'true');
      });
    }

    rows.forEach(row => {
      const priceCells = Array.from(row.querySelectorAll('td.price-number:not(.price-best)'));
      const priced = priceCells
        .map(cell => ({ cell, value: parsePrice(cell) }))
        .filter(item => item.value !== null);

      priced.forEach(({ cell }) => {
        cell.classList.remove('is-best', 'price-rank--best', 'price-rank--middle', 'price-rank--highest');
        cell.removeAttribute('data-price-rank');
      });

      if (!priced.length) return;

      const values = priced.map(item => item.value);
      const minimum = Math.min(...values);
      const maximum = Math.max(...values);
      const tied = minimum === maximum;

      priced.forEach(({ cell, value }) => {
        let rank = 'middle';
        let label = c.middle;

        if (tied || value === minimum) {
          rank = 'best';
          label = tied ? c.tie : c.best;
          cell.classList.add('is-best', 'price-rank--best');
        } else if (value === maximum) {
          rank = 'highest';
          label = c.highest;
          cell.classList.add('price-rank--highest');
        } else {
          cell.classList.add('price-rank--middle');
        }

        cell.dataset.priceRank = rank;
        cell.title = label;
        cell.setAttribute('aria-label', `${cell.textContent.trim()}. ${label}`);
      });
    });

    detail.querySelector('[data-price-ranking-legend]')?.remove();
    const wrap = table.closest('.price-table-wrap');
    wrap?.insertAdjacentHTML('beforebegin', rankingLegendMarkup());
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
    const existingCoverage = scaleSection?.querySelector('[data-price-coverage]');
    if (existingCoverage) existingCoverage.remove();
    scaleSection?.insertAdjacentHTML('beforeend', coverageMarkup());

    const sampleTitle = detail.querySelector('#price-sample-title');
    setText(sampleTitle, c.sampleTitle);
    const sampleHead = sampleTitle?.closest('.price-section__head');
    setText(sampleHead?.querySelector('p:not(.price-eyebrow)'), c.sampleBody);
    rankComparisonPrices(detail);

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
