(() => {
  const translations = {
    es: {
      'card.mediaLabel': 'Ver proyecto Mundial 2026',
      'card.imageAlt': 'Resumen del dashboard Mundial 2026',
      'card.label': 'Dashboard real · Google Apps Script',
      'card.title': 'Mundial 2026: análisis histórico y predicción',
      'card.body': 'Proyecto integral que combina preparación de datos, análisis histórico, modelado predictivo, automatización diaria y una experiencia web interactiva.',
      'card.full': 'Ver proyecto completo',
      'card.dashboard': 'Abrir dashboard',
      'card.code': 'Ver código',
      'dialog.close': 'Cerrar',
      'dialog.projects': 'Proyectos',
      'dialog.featured': 'Proyecto destacado',
      'dialog.title': 'Mundial 2026: análisis histórico y predicción',
      'dialog.intro': 'Una solución de datos de extremo a extremo: integra estadísticas históricas, genera predicciones iniciales y vivas, automatiza actualizaciones y publica los resultados en un dashboard web.',
      'dialog.dashboard': 'Abrir dashboard',
      'dialog.repo': 'Repositorio',
      'objective.title': 'Objetivo del proyecto',
      'objective.subtitle': 'Convertir múltiples fuentes deportivas en un producto analítico claro, reproducible y actualizable.',
      'objective.problemTitle': 'Problema abordado',
      'objective.problemBody': 'La información histórica, el calendario 2026, el ranking y los resultados recientes estaban distribuidos en estructuras diferentes. El proyecto los normaliza, valida y conecta con un modelo predictivo y una interfaz de consulta.',
      'metric.worldCups': 'Mundiales',
      'metric.matches': 'Partidos',
      'metric.teams': 'Selecciones',
      'live.title': 'Dashboard interactivo en calidad original',
      'live.subtitle': 'La aplicación real se presenta directamente para evitar capturas comprimidas. Utiliza su menú lateral para navegar entre las cuatro vistas.',
      'live.one.title': 'Resumen histórico',
      'live.one.body': 'Indicadores, campeones, goles y disciplina.',
      'live.two.title': 'Selecciones históricas',
      'live.two.body': 'Participaciones, resultados y mejores ediciones.',
      'live.three.title': 'Predicción inicial 2026',
      'live.three.body': 'Escenario base de grupos y eliminatorias.',
      'live.four.title': 'Predicción viva 2026',
      'live.four.body': 'Resultados confirmados y partidos pendientes.',
      'live.bar': 'Dashboard Mundial 2026',
      'live.newTab': 'Abrir en una pestaña nueva',
      'live.frameTitle': 'Dashboard interactivo Mundial 2026',
      'process.title': 'Proceso de desarrollo',
      'process.subtitle': 'Del dato bruto al dashboard publicado.',
      'process.one.title': 'Integración',
      'process.one.body': 'Históricos, calendario, ranking y resultados recientes.',
      'process.two.title': 'Preparación',
      'process.two.body': 'Limpieza, homologación y validación de campos.',
      'process.three.title': 'Predicción',
      'process.three.body': 'Modelo Poisson ajustado por ranking, Elo y forma.',
      'process.four.title': 'Publicación',
      'process.four.body': 'Apps Script, Chart.js y GitHub Actions.',
      'architecture.title': 'Arquitectura técnica',
      'architecture.subtitle': 'Componentes principales y flujo de información.',
      'architecture.sources.title': 'Fuentes',
      'architecture.sources.body': 'Históricos y ranking',
      'architecture.python.title': 'Python',
      'architecture.python.body': 'Limpieza y modelo',
      'architecture.sheets.title': 'Google Sheets',
      'architecture.sheets.body': 'Tablas y snapshots',
      'architecture.apps.title': 'Apps Script',
      'architecture.apps.body': 'Servicio y frontend',
      'architecture.chart.title': 'Chart.js',
      'architecture.chart.body': 'Visualización web',
      'code.title': 'Código completo y explicado',
      'code.subtitle': 'Selecciona un archivo. Primero se explica su función y después aparece el contenido completo con desplazamiento vertical y horizontal.',
      'code.appsTab': 'Google Apps Script',
      'code.pythonTab': 'Python y automatización',
      'code.selected': 'Archivo seleccionado',
      'code.input': 'Entrada',
      'code.output': 'Salida',
      'code.security': 'Seguridad',
      'code.github': 'Ver en GitHub',
      'code.copy': 'Copiar código completo',
      'code.select': 'Selecciona un archivo.',
      'results.title': 'Resultados',
      'results.subtitle': 'Un caso que demuestra análisis, automatización y desarrollo de producto de datos.',
      'results.players': 'Jugadores integrados.',
      'results.goals': 'Goles analizados.',
      'results.dailyValue': 'Diario',
      'results.daily': 'Actualización preparada.',
      'results.back': 'Volver a proyectos'
    },
    en: {
      'card.mediaLabel': 'View World Cup 2026 project',
      'card.imageAlt': 'World Cup 2026 dashboard overview',
      'card.label': 'Live dashboard · Google Apps Script',
      'card.title': 'World Cup 2026: historical analysis and prediction',
      'card.body': 'An end-to-end project combining data preparation, historical analysis, predictive modeling, daily automation, and an interactive web experience.',
      'card.full': 'View full project',
      'card.dashboard': 'Open dashboard',
      'card.code': 'View code',
      'dialog.close': 'Close',
      'dialog.projects': 'Projects',
      'dialog.featured': 'Featured project',
      'dialog.title': 'World Cup 2026: historical analysis and prediction',
      'dialog.intro': 'An end-to-end data solution that integrates historical statistics, generates initial and live predictions, automates updates, and publishes the results in a web dashboard.',
      'dialog.dashboard': 'Open dashboard',
      'dialog.repo': 'Repository',
      'objective.title': 'Project objective',
      'objective.subtitle': 'Turn multiple football data sources into a clear, reproducible, and maintainable analytical product.',
      'objective.problemTitle': 'Problem addressed',
      'objective.problemBody': 'Historical data, the 2026 schedule, rankings, and recent results came in different structures. The project normalizes and validates them, then connects the data to a predictive model and a queryable interface.',
      'metric.worldCups': 'World Cups',
      'metric.matches': 'Matches',
      'metric.teams': 'National teams',
      'live.title': 'Interactive dashboard in full quality',
      'live.subtitle': 'The live application is embedded directly instead of relying on compressed screenshots. Its side menu provides access to four views.',
      'live.one.title': 'Historical overview',
      'live.one.body': 'KPIs, champions, goals, and discipline.',
      'live.two.title': 'Historical teams',
      'live.two.body': 'Appearances, results, and best tournament finishes.',
      'live.three.title': 'Initial 2026 prediction',
      'live.three.body': 'Baseline scenario for groups and knockout rounds.',
      'live.four.title': 'Live 2026 prediction',
      'live.four.body': 'Confirmed results and remaining matches.',
      'live.bar': 'World Cup 2026 Dashboard',
      'live.newTab': 'Open in a new tab',
      'live.frameTitle': 'Interactive World Cup 2026 dashboard',
      'process.title': 'Development process',
      'process.subtitle': 'From raw data to a published dashboard.',
      'process.one.title': 'Integration',
      'process.one.body': 'Historical data, schedule, rankings, and recent results.',
      'process.two.title': 'Preparation',
      'process.two.body': 'Cleaning, standardization, and field validation.',
      'process.three.title': 'Prediction',
      'process.three.body': 'Poisson model adjusted with ranking, Elo, and recent form.',
      'process.four.title': 'Publishing',
      'process.four.body': 'Apps Script, Chart.js, and GitHub Actions.',
      'architecture.title': 'Technical architecture',
      'architecture.subtitle': 'Core components and information flow.',
      'architecture.sources.title': 'Sources',
      'architecture.sources.body': 'Historical data and rankings',
      'architecture.python.title': 'Python',
      'architecture.python.body': 'Cleaning and model',
      'architecture.sheets.title': 'Google Sheets',
      'architecture.sheets.body': 'Tables and snapshots',
      'architecture.apps.title': 'Apps Script',
      'architecture.apps.body': 'Service and frontend',
      'architecture.chart.title': 'Chart.js',
      'architecture.chart.body': 'Web visualization',
      'code.title': 'Full code, with context',
      'code.subtitle': 'Choose a file to see what it does first, then inspect the complete source with vertical and horizontal scrolling.',
      'code.appsTab': 'Google Apps Script',
      'code.pythonTab': 'Python and automation',
      'code.selected': 'Selected file',
      'code.input': 'Input',
      'code.output': 'Output',
      'code.security': 'Security',
      'code.github': 'View on GitHub',
      'code.copy': 'Copy full code',
      'code.select': 'Select a file.',
      'results.title': 'Results',
      'results.subtitle': 'A case that demonstrates analysis, automation, and data-product development.',
      'results.players': 'Players integrated.',
      'results.goals': 'Goals analyzed.',
      'results.dailyValue': 'Daily',
      'results.daily': 'Update workflow prepared.',
      'results.back': 'Back to projects'
    }
  };

  const fileTranslations = {
    es: {
      'Code.gs': ['Servidor y acceso a datos', 'Publica el Web App, lee las hojas históricas y predictivas y entrega al navegador los objetos que utiliza el dashboard.', 'Solicitud web y tablas de Google Sheets.', 'HTML evaluado y colecciones de datos.', 'Los IDs reales fueron sustituidos por marcadores; no se publican credenciales.'],
      'index.html': ['Estructura visual', 'Define navegación, filtros, indicadores, gráficos, tablas y contenedores de predicción.', 'Plantilla de Apps Script e información preparada por Code.gs.', 'DOM base de todas las vistas.', 'El recurso Base64 interno fue reemplazado por un marcador.'],
      'style.html': ['Diseño responsive', 'Contiene colores, tipografía, tarjetas, tablas, bracket y reglas para computadora y móvil.', 'Clases y elementos de index.html.', 'Presentación completa del dashboard.', 'No contiene credenciales; el recurso interno fue saneado.'],
      'script.html': ['Lógica y visualizaciones', 'Carga datos, normaliza estructuras, aplica filtros y dibuja métricas, gráficos, tablas y predicciones.', 'Respuesta de getDashboardData() y acciones del usuario.', 'Dashboard interactivo actualizado.', 'La versión publicada está saneada y omite datos privados.'],
      '01_prediccion_dinamica_2026.py': ['Modelo predictivo inicial', 'Carga calendario, ranking y estadísticas; calcula fortalezas, goles esperados y probabilidades para simular grupos y eliminatorias.', 'Calendario, ranking, Elo y forma reciente.', 'Predicción inicial completa.', 'Las credenciales se obtienen desde variables de entorno.'],
      '04_crear_fact_partidos_prediccion_2026.py': ['Tabla maestra del torneo', 'Une calendario, predicción inicial, predicción viva y resultados reales en una sola tabla.', 'Calendario y tablas predictivas.', 'fact_partidos_prediccion_2026.', 'El ID y las credenciales se reciben desde el entorno.'],
      'src/config.py': ['Configuración por entorno', 'Centraliza nombres de tablas, versión del modelo y variables requeridas por el pipeline.', 'Variables de entorno y GitHub Secrets.', 'Configuración validada.', 'No guarda secretos; solo los lee del entorno.'],
      'src/sheets_client.py': ['Cliente de Google Sheets', 'Encapsula autenticación y operaciones de lectura, escritura y anexado de DataFrames.', 'Cuenta de servicio, ID y nombre de hoja.', 'DataFrames y hojas actualizadas.', 'Llave privada y correo de servicio permanecen en el entorno.'],
      'prediccion_viva_mundial_2026.yml': ['Ejecución programada', 'Automatiza la instalación de dependencias y la actualización periódica de la predicción viva.', 'Código del repositorio y secretos configurados.', 'Ejecución programada del pipeline.', 'Los secretos se referencian por nombre y no se imprimen.']
    },
    en: {
      'Code.gs': ['Server and data access', 'Publishes the web app, reads historical and predictive sheets, and delivers the objects used by the dashboard to the browser.', 'Web request and Google Sheets tables.', 'Evaluated HTML and data collections.', 'Real IDs were replaced with placeholders; credentials are not published.'],
      'index.html': ['Visual structure', 'Defines navigation, filters, KPIs, charts, tables, and prediction containers.', 'Apps Script template and data prepared by Code.gs.', 'Base DOM for every view.', 'The internal Base64 resource was replaced with a placeholder.'],
      'style.html': ['Responsive design', 'Defines colors, typography, cards, tables, bracket layouts, and desktop/mobile rules.', 'Classes and elements from index.html.', 'Complete dashboard presentation.', 'Contains no credentials; the internal resource was sanitized.'],
      'script.html': ['Logic and visualizations', 'Loads data, normalizes structures, applies filters, and renders metrics, charts, tables, and predictions.', 'getDashboardData() response and user actions.', 'Updated interactive dashboard.', 'The published version is sanitized and omits private data.'],
      '01_prediccion_dinamica_2026.py': ['Initial predictive model', 'Loads the schedule, rankings, and statistics; estimates team strength, expected goals, and probabilities to simulate groups and knockout rounds.', 'Schedule, rankings, Elo, and recent form.', 'Complete initial prediction.', 'Credentials are obtained from environment variables.'],
      '04_crear_fact_partidos_prediccion_2026.py': ['Tournament master table', 'Combines schedule, initial prediction, live prediction, and real results into one table.', 'Schedule and prediction tables.', 'fact_partidos_prediccion_2026.', 'The ID and credentials are supplied through the environment.'],
      'src/config.py': ['Environment-based configuration', 'Centralizes table names, model version, and variables required by the pipeline.', 'Environment variables and GitHub Secrets.', 'Validated configuration.', 'Stores no secrets; it only reads them from the environment.'],
      'src/sheets_client.py': ['Google Sheets client', 'Encapsulates authentication plus DataFrame read, write, and append operations.', 'Service account, sheet ID, and sheet name.', 'DataFrames and updated sheets.', 'The private key and service-account email remain in the environment.'],
      'prediccion_viva_mundial_2026.yml': ['Scheduled execution', 'Automates dependency installation and periodic live-prediction updates.', 'Repository code and configured secrets.', 'Scheduled pipeline execution.', 'Secrets are referenced by name and are not printed.']
    }
  };

  function api() {
    return window.PortfolioI18n;
  }

  function t(key) {
    return api()?.t(`mundial.${key}`) ?? translations.es[key] ?? key;
  }

  function text(selector, key, root = document) {
    const element = root.querySelector(selector);
    if (element) element.textContent = t(key);
  }

  function attr(selector, name, key, root = document) {
    const element = root.querySelector(selector);
    if (element) element.setAttribute(name, t(key));
  }

  function applyFiles(root) {
    const locale = api()?.getLocale() || 'es';
    const files = fileTranslations[locale];
    root.querySelectorAll('.mw-file').forEach(button => {
      const name = button.querySelector('strong')?.textContent?.trim();
      const values = files[name];
      if (values) {
        const role = button.querySelector('span');
        if (role) role.textContent = values[0];
      }
    });

    const selectedName = root.querySelector('#mw-info-title')?.textContent?.trim();
    const values = files[selectedName];
    if (!values) return;
    text('#mw-info-title', null, root);
    const title = root.querySelector('#mw-info-title');
    const description = root.querySelector('#mw-info-description');
    const input = root.querySelector('#mw-info-input');
    const output = root.querySelector('#mw-info-output');
    const security = root.querySelector('#mw-info-security');
    if (title) title.textContent = selectedName;
    if (description) description.textContent = values[1];
    if (input) input.textContent = values[2];
    if (output) output.textContent = values[3];
    if (security) security.textContent = values[4];
  }

  function apply() {
    const card = document.querySelector('[data-portfolio-project="mundial-2026"].mw-card');
    const view = document.getElementById('mw-view');
    if (!card || !view) return;

    attr('#mw-open-media', 'aria-label', 'card.mediaLabel', card);
    attr('#mw-card-image', 'alt', 'card.imageAlt', card);
    text('.mw-card__label', 'card.label', card);
    text('h3', 'card.title', card);
    text('.mw-card__body > p', 'card.body', card);
    text('#mw-open', 'card.full', card);
    const cardLinks = card.querySelectorAll('.mw-actions a');
    if (cardLinks[0]) cardLinks[0].textContent = t('card.dashboard');
    if (cardLinks[1]) cardLinks[1].textContent = t('card.code');

    text('#mw-close', 'dialog.close', view);
    text('#mw-back-top', 'dialog.projects', view);
    text('.mw-kicker', 'dialog.featured', view);
    text('#mw-title', 'dialog.title', view);
    text('.mw-hero > div:first-child > p:last-child', 'dialog.intro', view);
    const heroLinks = view.querySelectorAll('.mw-hero__actions a');
    if (heroLinks[0]) heroLinks[0].textContent = t('dialog.dashboard');
    if (heroLinks[1]) heroLinks[1].textContent = t('dialog.repo');

    const sections = view.querySelectorAll('.mw-section');
    if (sections[0]) {
      text('.mw-section__head h3', 'objective.title', sections[0]);
      text('.mw-section__head p', 'objective.subtitle', sections[0]);
      text('.mw-panel h4', 'objective.problemTitle', sections[0]);
      text('.mw-panel p', 'objective.problemBody', sections[0]);
      const metrics = sections[0].querySelectorAll('.mw-metric span');
      [t('metric.worldCups'), t('metric.matches'), t('metric.teams')].forEach((value, index) => { if (metrics[index]) metrics[index].textContent = value; });
    }

    if (sections[1]) {
      text('.mw-section__head h3', 'live.title', sections[1]);
      text('.mw-section__head p', 'live.subtitle', sections[1]);
      const guides = sections[1].querySelectorAll('.mw-live-guide article');
      const guideKeys = ['one', 'two', 'three', 'four'];
      guideKeys.forEach((name, index) => {
        if (!guides[index]) return;
        const title = guides[index].querySelector('strong');
        const body = guides[index].querySelector('span');
        if (title) title.textContent = t(`live.${name}.title`);
        if (body) body.textContent = t(`live.${name}.body`);
      });
      text('.mw-live__bar strong', 'live.bar', sections[1]);
      text('.mw-live__bar a', 'live.newTab', sections[1]);
      attr('iframe', 'title', 'live.frameTitle', sections[1]);
    }

    if (sections[2]) {
      text('.mw-section__head h3', 'process.title', sections[2]);
      text('.mw-section__head p', 'process.subtitle', sections[2]);
      const steps = sections[2].querySelectorAll('.mw-step');
      ['one', 'two', 'three', 'four'].forEach((name, index) => {
        if (!steps[index]) return;
        const title = steps[index].querySelector('h4');
        const body = steps[index].querySelector('p');
        if (title) title.textContent = t(`process.${name}.title`);
        if (body) body.textContent = t(`process.${name}.body`);
      });
    }

    if (sections[3]) {
      text('.mw-section__head h3', 'architecture.title', sections[3]);
      text('.mw-section__head p', 'architecture.subtitle', sections[3]);
      const nodes = sections[3].querySelectorAll('.mw-node');
      const names = ['sources', 'python', 'sheets', 'apps', 'chart'];
      names.forEach((name, index) => {
        if (!nodes[index]) return;
        nodes[index].innerHTML = `<b>${t(`architecture.${name}.title`)}</b>${t(`architecture.${name}.body`)}`;
      });
    }

    if (sections[4]) {
      text('.mw-section__head h3', 'code.title', sections[4]);
      text('.mw-section__head p', 'code.subtitle', sections[4]);
      const tabs = sections[4].querySelectorAll('.mw-code-tab');
      if (tabs[0]) tabs[0].textContent = t('code.appsTab');
      if (tabs[1]) tabs[1].textContent = t('code.pythonTab');
      text('.mw-info-label', 'code.selected', sections[4]);
      const labels = sections[4].querySelectorAll('.mw-info-grid strong');
      [t('code.input'), t('code.output'), t('code.security')].forEach((value, index) => { if (labels[index]) labels[index].textContent = value; });
      text('#mw-code-source', 'code.github', sections[4]);
      const copy = sections[4].querySelector('#mw-copy');
      if (copy && !/copiado|copied|pudo|could not/i.test(copy.textContent)) copy.textContent = t('code.copy');
      const code = sections[4].querySelector('#mw-code-content');
      if (code && /^(Selecciona un archivo\.|Select a file\.)$/.test(code.textContent.trim())) code.textContent = t('code.select');
      applyFiles(sections[4]);
    }

    if (sections[5]) {
      text('.mw-section__head h3', 'results.title', sections[5]);
      text('.mw-section__head p', 'results.subtitle', sections[5]);
      const results = sections[5].querySelectorAll('.mw-result');
      if (results[0]?.querySelector('p')) results[0].querySelector('p').textContent = t('results.players');
      if (results[1]?.querySelector('p')) results[1].querySelector('p').textContent = t('results.goals');
      if (results[2]?.querySelector('strong')) results[2].querySelector('strong').textContent = t('results.dailyValue');
      if (results[2]?.querySelector('p')) results[2].querySelector('p').textContent = t('results.daily');
      text('#mw-back-bottom', 'results.back', sections[5]);
    }
  }

  function mount() {
    if (!api()) {
      console.error('Mundial 2026 i18n requiere PortfolioI18n.');
      return;
    }
    api().registerCatalog('mundial', translations);
    apply();
    api().onChange(() => queueMicrotask(apply));

    const view = document.getElementById('mw-view');
    if (view) {
      view.addEventListener('click', event => {
        if (event.target.closest('.mw-file, .mw-code-tab, #mw-open, #mw-copy')) {
          queueMicrotask(apply);
        }
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
