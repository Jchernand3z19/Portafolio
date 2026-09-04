(() => {
  const BUILD = '20260904-portfolio-i18n-prices';

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = `${src}?v=${BUILD}`;
      script.defer = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`No se pudo cargar ${src}`));
      document.body.appendChild(script);
    });
  }

  function loadStylesheet(href) {
    const style = document.createElement('link');
    style.rel = 'stylesheet';
    style.href = `${href}?v=${BUILD}`;
    document.head.appendChild(style);
  }

  function rewriteLegacyProjectUrl(value) {
    if (typeof value !== 'string') return value;

    return value
      .replaceAll('assets/mundial/', 'mundial-2026/portfolio/assets/dashboard/')
      .replaceAll('assets/code/apps-script/', 'mundial-2026/dashboard/apps-script/')
      .replaceAll('mundial-2026-predicciones/', 'mundial-2026/');
  }

  function rewriteLegacyProjectLinks(root = document) {
    if (!root?.querySelectorAll) return;

    root.querySelectorAll('a[href]').forEach(anchor => {
      const currentHref = anchor.getAttribute('href');
      const rewrittenHref = rewriteLegacyProjectUrl(currentHref);
      if (rewrittenHref && rewrittenHref !== currentHref) {
        anchor.setAttribute('href', rewrittenHref);
      }
    });
  }

  function setupLegacyProjectCompatibility() {
    if (!window.__portfolioAssetCacheFix) {
      const nativeFetch = window.fetch.bind(window);

      window.fetch = (input, init) => {
        if (typeof input !== 'string') return nativeFetch(input, init);

        const rewrittenInput = rewriteLegacyProjectUrl(input);
        if (
          rewrittenInput.includes('mundial-2026/') ||
          rewrittenInput.includes('assets/projects/')
        ) {
          const url = new URL(rewrittenInput, window.location.href);
          url.searchParams.set('assetfix', BUILD);
          return nativeFetch(url.toString(), init);
        }

        return nativeFetch(rewrittenInput, init);
      };

      window.__portfolioAssetCacheFix = true;
    }

    rewriteLegacyProjectLinks();

    if (!window.__portfolioLegacyLinkObserver && 'MutationObserver' in window) {
      const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
          if (mutation.type === 'attributes') {
            rewriteLegacyProjectLinks(mutation.target.parentElement || document);
            return;
          }

          mutation.addedNodes.forEach(node => {
            if (node.nodeType === Node.ELEMENT_NODE) {
              rewriteLegacyProjectLinks(node);
              if (node.matches?.('a[href]')) {
                const currentHref = node.getAttribute('href');
                const rewrittenHref = rewriteLegacyProjectUrl(currentHref);
                if (rewrittenHref && rewrittenHref !== currentHref) {
                  node.setAttribute('href', rewrittenHref);
                }
              }
            }
          });
        });
      });

      observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['href']
      });

      window.__portfolioLegacyLinkObserver = observer;
    }
  }

  function updateMenuLabel(toggle, open) {
    const key = open ? 'site.nav.menuClose' : 'site.nav.menuOpen';
    const fallback = open ? 'Cerrar menú de navegación' : 'Abrir menú de navegación';
    toggle.setAttribute('aria-label', window.PortfolioI18n?.t(key) || fallback);
  }

  function setupSite() {
    const toggle = document.getElementById('menu-toggle');
    const links = document.getElementById('nav-links');
    if (toggle && links) {
      toggle.addEventListener('click', () => {
        const open = links.classList.toggle('is-open');
        toggle.setAttribute('aria-expanded', String(open));
        updateMenuLabel(toggle, open);
      });
      links.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
        links.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
        updateMenuLabel(toggle, false);
      }));
    }

    const items = Array.from(document.querySelectorAll('.fade-in'));
    if ('IntersectionObserver' in window) {
      const appearanceObserver = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            appearanceObserver.unobserve(entry.target);
          }
        });
      }, { threshold: .12 });
      items.forEach(item => appearanceObserver.observe(item));
    } else {
      items.forEach(item => item.classList.add('is-visible'));
    }

    const sections = Array.from(document.querySelectorAll('[data-section]'));
    const navLinks = Array.from(document.querySelectorAll('.nav__link'));
    const progressDots = Array.from(document.querySelectorAll('.scroll-progress__dot'));

    function setActiveSection(id) {
      navLinks.forEach(link => link.classList.remove('is-active'));
      progressDots.forEach(dot => dot.classList.remove('is-active'));

      const currentLink = navLinks.find(link => link.getAttribute('href') === `#${id}`);
      const currentDot = progressDots.find(dot => dot.dataset.sectionDot === id);
      if (currentLink) currentLink.classList.add('is-active');
      if (currentDot) currentDot.classList.add('is-active');
    }

    if ('IntersectionObserver' in window) {
      const activeSectionObserver = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) setActiveSection(entry.target.id);
        });
      }, { rootMargin: '-45% 0px -45% 0px', threshold: 0 });
      sections.forEach(section => activeSectionObserver.observe(section));
    } else if (sections.length) {
      setActiveSection(sections[0].id);
    }

    const progressFill = document.getElementById('scroll-progress-fill');
    function updateProgressFill() {
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      const percentage = maxScroll > 0
        ? Math.min(100, Math.max(0, (window.scrollY / maxScroll) * 100))
        : 0;
      if (progressFill) progressFill.style.height = `${percentage}%`;
    }

    window.addEventListener('scroll', updateProgressFill, { passive: true });
    window.addEventListener('resize', updateProgressFill);
    updateProgressFill();

    setupLegacyProjectCompatibility();

    const projectStyles = [
      'css/i18n.css',
      'mundial-2026/portfolio/mundial-2026.css',
      'precios-supermercados-sps/portfolio/precios-portfolio.css'
    ];

    const projectModules = [
      'mundial-2026/portfolio/mundial-2026.js',
      'mundial-2026/portfolio/mundial-2026-i18n.js',
      'precios-supermercados-sps/portfolio/precios-portfolio.js'
    ];

    projectStyles.forEach(loadStylesheet);

    loadScript('js/i18n.js')
      .then(() => loadScript('js/projects/registry.js'))
      .then(() => {
        window.PortfolioProjects?.prepare();
        return projectModules.reduce(
          (sequence, module) => sequence.then(() => loadScript(module)),
          Promise.resolve()
        );
      })
      .then(() => {
        rewriteLegacyProjectLinks();
        window.PortfolioI18n?.refresh();
      })
      .catch(error => {
        console.error('No se pudieron cargar los proyectos del portafolio.', error);
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupSite);
  } else {
    setupSite();
  }
})();
