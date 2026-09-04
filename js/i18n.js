(() => {
  const DEFAULT_LOCALE = 'es';
  const SUPPORTED_LOCALES = Object.freeze(['es', 'en']);
  const STORAGE_KEY = 'portfolio.locale.v1';
  const catalogs = new Map();
  const subscribers = new Set();

  const siteCatalog = {
    es: {
      'meta.title': 'Juan Carlos Hernández Ramos — Especialista en Reportes, Dashboards y Automatización de Datos',
      'meta.description': 'Portafolio profesional de Juan Carlos Hernández Ramos, Especialista en Reportes, Dashboards y Automatización de Datos con más de 5 años de experiencia.',
      'meta.ogTitle': 'Juan Carlos Hernández Ramos — Especialista en Reportes, Dashboards y Automatización',
      'meta.ogDescription': '5+ años de experiencia en reportes comerciales, inteligencia de negocios y automatización de procesos.',
      'meta.jobTitle': 'Especialista en Reportes, Dashboards y Automatización de Datos',
      'skip.main': 'Saltar al contenido principal',
      'nav.mainLabel': 'Navegación principal',
      'nav.homeLabel': 'Ir al inicio',
      'nav.menuOpen': 'Abrir menú de navegación',
      'nav.menuClose': 'Cerrar menú de navegación',
      'nav.home': 'Inicio',
      'nav.solutions': 'Soluciones',
      'nav.experience': 'Experiencia',
      'nav.tools': 'Herramientas',
      'nav.projects': 'Proyectos',
      'nav.contact': 'Contacto',
      'language.group': 'Idioma del portafolio',
      'language.es': 'Cambiar idioma a español',
      'language.en': 'Change language to English',
      'hero.eyebrow': '5+ años de experiencia · Avery Dennison · PAE Global · Gildan',
      'hero.title': 'Especialista en Reportes, Dashboards y Automatización de Datos',
      'hero.subtitle': 'Desarrollo dashboards, automatizaciones y procesos de preparación de datos que convierten distintas fuentes de información en soluciones claras, actualizables y orientadas al análisis.<span class="hero__stack">Excel · Google Sheets · Power BI · Looker Studio · Apps Script</span>',
      'hero.identity': 'Juan Carlos Hernández Ramos — Analista de Datos',
      'hero.availability': '<span class="hero__availability-dot" aria-hidden="true"></span>Disponible para nuevas oportunidades · Presencial · Híbrido · Remoto',
      'hero.projects': 'Explorar proyectos',
      'hero.contact': 'Contactar',
      'solutions.title': 'Soluciones',
      'solutions.intro': 'Trabajo el ciclo completo de la información: preparación, análisis, automatización y presentación de resultados. Servicios: Analítica empresarial, elaboración de informes y automatización de procesos.',
      'solutions.dashboard.title': 'Dashboards',
      'solutions.dashboard.body': 'Visualizaciones ejecutivas e interactivas para consultar indicadores, comparar resultados e identificar tendencias desde una sola vista.',
      'solutions.automation.title': 'Automatización',
      'solutions.automation.body': 'Flujos que reciben, limpian, consolidan y publican información, reduciendo tareas repetitivas y tiempos de actualización.',
      'solutions.prep.title': 'Preparación de datos',
      'solutions.prep.body': 'Limpieza, homologación, transformación y validación de datos para construir estructuras confiables y listas para análisis.',
      'solutions.analysis.title': 'Análisis',
      'solutions.analysis.body': 'Definición de métricas, evaluación de resultados y análisis de negocio para convertir los datos en información accionable.',
      'experience.title': 'Experiencia Profesional',
      'experience.intro': 'Trayectoria en Avery Dennison, PAE Global y Gildan. Especialización en reportería comercial, operativa y de eficiencia.',
      'experience.commercial.badge': 'Comercial',
      'experience.commercial.title': 'Comercial',
      'experience.commercial.body': 'Análisis de ventas, metas, forecast mensual, pedidos, comportamiento por producto y seguimiento de resultados ejecutivos.',
      'experience.operations.badge': 'Operaciones',
      'experience.operations.title': 'Operaciones y Manufactura',
      'experience.operations.body': 'Transformación de reportes manuales, seguimiento de indicadores productivos y visualización de resultados operativos.',
      'experience.banking.badge': 'Banca',
      'experience.banking.title': 'Banca',
      'experience.banking.body': 'Análisis comercial de clientes y productos, prospección y reportería para dar seguimiento a resultados del negocio.',
      'tools.title': 'Herramientas',
      'tools.intro': 'Las herramientas se seleccionan según el problema, la fuente de información y el tipo de solución requerida.',
      'tools.visualization': 'Visualización',
      'tools.preparation': 'Preparación y Análisis',
      'tools.automation': 'Automatización',
      'tools.sources': 'Fuentes y Plataformas',
      'tools.excel': 'Excel Avanzado',
      'tools.pythonAutomation': 'Python para automatización',
      'projects.title': 'Proyectos',
      'projects.intro': 'Casos que muestran el trabajo técnico detrás de los dashboards, desde la preparación de datos hasta la experiencia final.',
      'contact.title': 'Contacto',
      'contact.prompt': '¿Tienes un proyecto en mente? Hablemos.',
      'footer.role': 'Especialista en Reportes, Dashboards y Automatización de Datos',
      'footer.motto': '“Transformando datos en decisiones”',
      'footer.made': 'Hecho con Python y precisión',
      'legacy.close': 'Cerrar',
      'legacy.objective': 'Objetivo',
      'legacy.preview': 'Vista del proyecto',
      'legacy.live': 'Abrir dashboard interactivo real',
      'legacy.process': 'Proceso de desarrollo',
      'legacy.technical': 'Estructura técnica',
      'legacy.structure': 'Estructura del proyecto',
      'legacy.snippet': 'Fragmento representativo',
      'legacy.results': 'Resultados medibles',
      'progress.label': 'Progreso de navegación'
    },
    en: {
      'meta.title': 'Juan Carlos Hernández Ramos — Reporting, Dashboard & Data Automation Specialist',
      'meta.description': 'Professional portfolio of Juan Carlos Hernández Ramos, focused on reporting, dashboards, data preparation and process automation with 5+ years of experience.',
      'meta.ogTitle': 'Juan Carlos Hernández Ramos — Reporting, Dashboard & Data Automation Specialist',
      'meta.ogDescription': '5+ years of experience in commercial reporting, business intelligence, dashboards and process automation.',
      'meta.jobTitle': 'Reporting, Dashboard & Data Automation Specialist',
      'skip.main': 'Skip to main content',
      'nav.mainLabel': 'Primary navigation',
      'nav.homeLabel': 'Go to home',
      'nav.menuOpen': 'Open navigation menu',
      'nav.menuClose': 'Close navigation menu',
      'nav.home': 'Home',
      'nav.solutions': 'Solutions',
      'nav.experience': 'Experience',
      'nav.tools': 'Tools',
      'nav.projects': 'Projects',
      'nav.contact': 'Contact',
      'language.group': 'Portfolio language',
      'language.es': 'Cambiar idioma a español',
      'language.en': 'Change language to English',
      'hero.eyebrow': '5+ years of experience · Avery Dennison · PAE Global · Gildan',
      'hero.title': 'Reporting, Dashboard & Data Automation Specialist',
      'hero.subtitle': 'I build dashboards, automations, and data preparation workflows that turn information from multiple sources into clear, maintainable solutions designed for analysis.<span class="hero__stack">Excel · Google Sheets · Power BI · Looker Studio · Apps Script</span>',
      'hero.identity': 'Juan Carlos Hernández Ramos — Data Analyst',
      'hero.availability': '<span class="hero__availability-dot" aria-hidden="true"></span>Open to new opportunities · On-site · Hybrid · Remote',
      'hero.projects': 'Explore projects',
      'hero.contact': 'Contact me',
      'solutions.title': 'Solutions',
      'solutions.intro': 'I work across the information lifecycle: data preparation, analysis, automation, and presentation. My work includes business analytics, reporting, and process automation.',
      'solutions.dashboard.title': 'Dashboards',
      'solutions.dashboard.body': 'Executive and interactive views for tracking KPIs, comparing results, and identifying trends from a single interface.',
      'solutions.automation.title': 'Automation',
      'solutions.automation.body': 'Workflows that receive, clean, consolidate, and publish information to reduce repetitive work and shorten update cycles.',
      'solutions.prep.title': 'Data preparation',
      'solutions.prep.body': 'Cleaning, standardization, transformation, and validation to build reliable structures that are ready for analysis.',
      'solutions.analysis.title': 'Analysis',
      'solutions.analysis.body': 'Metric definition, performance evaluation, and business analysis that turn data into actionable information.',
      'experience.title': 'Professional Experience',
      'experience.intro': 'Experience across Avery Dennison, PAE Global, and Gildan, with a focus on commercial, operational, and efficiency reporting.',
      'experience.commercial.badge': 'Commercial',
      'experience.commercial.title': 'Commercial',
      'experience.commercial.body': 'Sales, target, monthly forecast, order, product-performance, and executive-results analysis.',
      'experience.operations.badge': 'Operations',
      'experience.operations.title': 'Operations & Manufacturing',
      'experience.operations.body': 'Transformation of manual reports, production KPI tracking, and visualization of operational results.',
      'experience.banking.badge': 'Banking',
      'experience.banking.title': 'Banking',
      'experience.banking.body': 'Commercial analysis of customers and products, prospecting, and reporting used to track business performance.',
      'tools.title': 'Tools',
      'tools.intro': 'I select tools based on the problem, the information source, and the type of solution required.',
      'tools.visualization': 'Visualization',
      'tools.preparation': 'Preparation & Analysis',
      'tools.automation': 'Automation',
      'tools.sources': 'Sources & Platforms',
      'tools.excel': 'Advanced Excel',
      'tools.pythonAutomation': 'Python for automation',
      'projects.title': 'Projects',
      'projects.intro': 'Cases that show the technical work behind the dashboards, from data preparation to the final user experience.',
      'contact.title': 'Contact',
      'contact.prompt': 'Have a project in mind? Let’s talk.',
      'footer.role': 'Reporting, Dashboard & Data Automation Specialist',
      'footer.motto': '“Turning data into decisions”',
      'footer.made': 'Built with Python and precision',
      'legacy.close': 'Close',
      'legacy.objective': 'Objective',
      'legacy.preview': 'Project view',
      'legacy.live': 'Open live interactive dashboard',
      'legacy.process': 'Development process',
      'legacy.technical': 'Technical structure',
      'legacy.structure': 'Project structure',
      'legacy.snippet': 'Representative snippet',
      'legacy.results': 'Measurable results',
      'progress.label': 'Navigation progress'
    }
  };

  function validateCatalog(namespace, translations) {
    if (!translations || typeof translations !== 'object') {
      throw new Error(`Catálogo i18n inválido: ${namespace}`);
    }

    const baseline = Object.keys(translations[DEFAULT_LOCALE] || {}).sort();
    if (!baseline.length) throw new Error(`Catálogo i18n vacío: ${namespace}`);

    SUPPORTED_LOCALES.forEach(locale => {
      const entries = translations[locale];
      if (!entries || typeof entries !== 'object') {
        throw new Error(`Falta locale ${locale} en ${namespace}`);
      }
      const keys = Object.keys(entries).sort();
      if (keys.length !== baseline.length || keys.some((key, index) => key !== baseline[index])) {
        throw new Error(`Keys i18n incompletas en ${namespace}:${locale}`);
      }
      keys.forEach(key => {
        if (typeof entries[key] !== 'string' || !entries[key].trim()) {
          throw new Error(`Valor i18n vacío en ${namespace}:${locale}:${key}`);
        }
      });
    });
  }

  function registerCatalog(namespace, translations) {
    if (!namespace || catalogs.has(namespace)) {
      if (catalogs.has(namespace)) return false;
      throw new Error('El namespace i18n es obligatorio.');
    }
    validateCatalog(namespace, translations);
    catalogs.set(namespace, translations);
    return true;
  }

  registerCatalog('site', siteCatalog);

  function safeReadLocale() {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      return SUPPORTED_LOCALES.includes(stored) ? stored : null;
    } catch (error) {
      return null;
    }
  }

  function safeWriteLocale(value) {
    try {
      window.localStorage.setItem(STORAGE_KEY, value);
    } catch (error) {
      // Storage can be blocked. Locale remains valid for the current page.
    }
  }

  let currentLocale = safeReadLocale() || DEFAULT_LOCALE;

  function interpolate(value, variables) {
    return value.replace(/\{([a-zA-Z0-9_]+)\}/g, (match, name) => (
      Object.prototype.hasOwnProperty.call(variables, name) ? String(variables[name]) : match
    ));
  }

  function t(fullKey, variables = {}) {
    const separator = fullKey.indexOf('.');
    const namespace = separator > 0 ? fullKey.slice(0, separator) : 'site';
    const key = separator > 0 ? fullKey.slice(separator + 1) : fullKey;
    const catalog = catalogs.get(namespace);
    if (!catalog) return fullKey;
    const value = catalog[currentLocale]?.[key] ?? catalog[DEFAULT_LOCALE]?.[key];
    return typeof value === 'string' ? interpolate(value, variables) : fullKey;
  }

  const textBindings = [
    ['.skip-link', 'site.skip.main'],
    ['#nav-links li:nth-child(1) .nav__link', 'site.nav.home'],
    ['#nav-links li:nth-child(2) .nav__link', 'site.nav.solutions'],
    ['#nav-links li:nth-child(3) .nav__link', 'site.nav.experience'],
    ['#nav-links li:nth-child(4) .nav__link', 'site.nav.tools'],
    ['#nav-links li:nth-child(5) .nav__link', 'site.nav.projects'],
    ['#nav-links li:nth-child(6) .nav__link', 'site.nav.contact'],
    ['#inicio .hero__eyebrow', 'site.hero.eyebrow'],
    ['#inicio h1', 'site.hero.title'],
    ['#inicio .hero__identity', 'site.hero.identity'],
    ['#inicio .hero__actions .button:nth-child(1)', 'site.hero.projects'],
    ['#inicio .hero__actions .button:nth-child(2)', 'site.hero.contact'],
    ['#soluciones .section-heading h2', 'site.solutions.title'],
    ['#soluciones .section-heading p', 'site.solutions.intro'],
    ['#soluciones .solution-card:nth-child(1) h3', 'site.solutions.dashboard.title'],
    ['#soluciones .solution-card:nth-child(1) p', 'site.solutions.dashboard.body'],
    ['#soluciones .solution-card:nth-child(2) h3', 'site.solutions.automation.title'],
    ['#soluciones .solution-card:nth-child(2) p', 'site.solutions.automation.body'],
    ['#soluciones .solution-card:nth-child(3) h3', 'site.solutions.prep.title'],
    ['#soluciones .solution-card:nth-child(3) p', 'site.solutions.prep.body'],
    ['#soluciones .solution-card:nth-child(4) h3', 'site.solutions.analysis.title'],
    ['#soluciones .solution-card:nth-child(4) p', 'site.solutions.analysis.body'],
    ['#experiencia .section-heading h2', 'site.experience.title'],
    ['#experiencia .section-heading p', 'site.experience.intro'],
    ['#experiencia .experience-card:nth-child(1) .badge', 'site.experience.commercial.badge'],
    ['#experiencia .experience-card:nth-child(1) h3', 'site.experience.commercial.title'],
    ['#experiencia .experience-card:nth-child(1) p', 'site.experience.commercial.body'],
    ['#experiencia .experience-card:nth-child(2) .badge', 'site.experience.operations.badge'],
    ['#experiencia .experience-card:nth-child(2) h3', 'site.experience.operations.title'],
    ['#experiencia .experience-card:nth-child(2) p', 'site.experience.operations.body'],
    ['#experiencia .experience-card:nth-child(3) .badge', 'site.experience.banking.badge'],
    ['#experiencia .experience-card:nth-child(3) h3', 'site.experience.banking.title'],
    ['#experiencia .experience-card:nth-child(3) p', 'site.experience.banking.body'],
    ['#herramientas .section-heading h2', 'site.tools.title'],
    ['#herramientas .section-heading p', 'site.tools.intro'],
    ['#herramientas .tool-group:nth-child(1) h3', 'site.tools.visualization'],
    ['#herramientas .tool-group:nth-child(2) h3', 'site.tools.preparation'],
    ['#herramientas .tool-group:nth-child(3) h3', 'site.tools.automation'],
    ['#herramientas .tool-group:nth-child(4) h3', 'site.tools.sources'],
    ['#herramientas .tool-group:nth-child(2) li:nth-child(3)', 'site.tools.excel'],
    ['#herramientas .tool-group:nth-child(3) li:nth-child(2)', 'site.tools.pythonAutomation'],
    ['#proyectos .section-heading h2', 'site.projects.title'],
    ['#proyectos .section-heading p', 'site.projects.intro'],
    ['#contacto h2', 'site.contact.title'],
    ['#contacto h3', 'site.contact.prompt'],
    ['.footer-brand p:nth-of-type(1)', 'site.footer.role'],
    ['.footer-brand p:nth-of-type(2)', 'site.footer.motto'],
    ['.footer-nav a:nth-child(1)', 'site.nav.home'],
    ['.footer-nav a:nth-child(2)', 'site.nav.solutions'],
    ['.footer-nav a:nth-child(3)', 'site.nav.experience'],
    ['.footer-nav a:nth-child(4)', 'site.nav.tools'],
    ['.footer-nav a:nth-child(5)', 'site.nav.projects'],
    ['.footer-nav a:nth-child(6)', 'site.nav.contact'],
    ['.footer-bottom span:nth-child(2)', 'site.footer.made'],
    ['#project-close', 'site.legacy.close'],
    ['#breadcrumb-projects', 'site.nav.projects'],
    ['#project-view .objective-box h3', 'site.legacy.objective'],
    ['#detail-preview-label', 'site.legacy.preview'],
    ['#detail-live-link', 'site.legacy.live'],
    ['#project-view .detail-section:nth-of-type(1) h2', 'site.legacy.process'],
    ['#project-view .detail-section:nth-of-type(2) h2', 'site.legacy.technical'],
    ['#project-view .code-card:nth-child(1) h3', 'site.legacy.structure'],
    ['#project-view .code-card:nth-child(2) h3', 'site.legacy.snippet'],
    ['#project-view .detail-section:nth-of-type(3) h2', 'site.legacy.results']
  ];

  const htmlBindings = [
    ['#inicio .hero__subtitle', 'site.hero.subtitle'],
    ['#inicio .hero__availability', 'site.hero.availability']
  ];

  function setText(selector, key) {
    const element = document.querySelector(selector);
    if (element) element.textContent = t(key);
  }

  function updateMetadata() {
    document.documentElement.lang = currentLocale;
    document.title = t('site.meta.title');

    const description = document.querySelector('meta[name="description"]');
    const ogTitle = document.querySelector('meta[property="og:title"]');
    const ogDescription = document.querySelector('meta[property="og:description"]');
    if (description) description.content = t('site.meta.description');
    if (ogTitle) ogTitle.content = t('site.meta.ogTitle');
    if (ogDescription) ogDescription.content = t('site.meta.ogDescription');

    const schema = document.querySelector('script[type="application/ld+json"]');
    if (schema) {
      try {
        const payload = JSON.parse(schema.textContent);
        payload.jobTitle = t('site.meta.jobTitle');
        schema.textContent = JSON.stringify(payload, null, 2);
      } catch (error) {
        // Invalid structured data should not break the language control.
      }
    }
  }

  function updateAccessibleLabels() {
    const nav = document.querySelector('.site-header .nav');
    const brand = document.querySelector('.site-header .brand[href="#inicio"]');
    const toggle = document.getElementById('menu-toggle');
    const progress = document.querySelector('.scroll-progress');
    const footer = document.querySelector('.footer-nav');

    if (nav) nav.setAttribute('aria-label', t('site.nav.mainLabel'));
    if (brand) brand.setAttribute('aria-label', t('site.nav.homeLabel'));
    if (toggle) {
      const isOpen = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-label', t(isOpen ? 'site.nav.menuClose' : 'site.nav.menuOpen'));
    }
    if (progress) progress.setAttribute('aria-label', t('site.progress.label'));
    if (footer) footer.setAttribute('aria-label', currentLocale === 'es' ? 'Navegación del pie' : 'Footer navigation');

    const dots = document.querySelectorAll('.scroll-progress__dot');
    const dotKeys = ['nav.home', 'nav.solutions', 'nav.experience', 'nav.tools', 'nav.projects', 'nav.contact'];
    dots.forEach((dot, index) => {
      if (dotKeys[index]) dot.setAttribute('aria-label', t(`site.${dotKeys[index]}`));
    });
  }

  function createLanguageSwitcher() {
    if (document.getElementById('portfolio-language-switcher')) return;
    const nav = document.querySelector('.site-header .nav');
    const links = document.getElementById('nav-links');
    const toggle = document.getElementById('menu-toggle');
    if (!nav || !links || !toggle) return;

    const controls = document.createElement('div');
    controls.className = 'nav__controls';

    const switcher = document.createElement('div');
    switcher.id = 'portfolio-language-switcher';
    switcher.className = 'language-switcher';
    switcher.setAttribute('role', 'group');

    SUPPORTED_LOCALES.forEach(locale => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'language-switcher__option';
      button.dataset.locale = locale;
      button.textContent = locale.toUpperCase();
      button.addEventListener('click', () => setLocale(locale));
      switcher.appendChild(button);
    });

    controls.appendChild(switcher);
    controls.appendChild(toggle);
    nav.appendChild(controls);
  }

  function updateLanguageSwitcher() {
    const switcher = document.getElementById('portfolio-language-switcher');
    if (!switcher) return;
    switcher.setAttribute('aria-label', t('site.language.group'));
    switcher.querySelectorAll('[data-locale]').forEach(button => {
      const locale = button.dataset.locale;
      const active = locale === currentLocale;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
      button.setAttribute('aria-label', t(`site.language.${locale}`));
    });
  }

  function applySite() {
    updateMetadata();
    textBindings.forEach(([selector, key]) => setText(selector, key));
    htmlBindings.forEach(([selector, key]) => {
      const element = document.querySelector(selector);
      if (element) element.innerHTML = t(key);
    });
    updateAccessibleLabels();
    updateLanguageSwitcher();
  }

  function setLocale(value, options = {}) {
    const next = SUPPORTED_LOCALES.includes(value) ? value : DEFAULT_LOCALE;
    const changed = next !== currentLocale;
    currentLocale = next;
    if (options.persist !== false) safeWriteLocale(next);
    applySite();

    if (changed || options.force === true) {
      const detail = Object.freeze({ locale: currentLocale });
      subscribers.forEach(handler => handler(detail));
      window.dispatchEvent(new CustomEvent('portfolio:localechange', { detail }));
    }
    return currentLocale;
  }

  function onChange(handler) {
    if (typeof handler !== 'function') return () => {};
    subscribers.add(handler);
    return () => subscribers.delete(handler);
  }

  function refresh() {
    applySite();
  }

  window.PortfolioI18n = Object.freeze({
    defaultLocale: DEFAULT_LOCALE,
    supportedLocales: SUPPORTED_LOCALES,
    getLocale: () => currentLocale,
    setLocale,
    t,
    registerCatalog,
    onChange,
    refresh
  });

  createLanguageSwitcher();
  applySite();
  window.dispatchEvent(new CustomEvent('portfolio:i18n-ready', {
    detail: Object.freeze({ locale: currentLocale })
  }));
})();
