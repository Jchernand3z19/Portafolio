(() => {
  const BUILD = '20260904-project-detail-standard-v1';

  function loadStyle(href) {
    if (document.querySelector(`link[data-portfolio-standard="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `${href}?v=${BUILD}`;
    link.dataset.portfolioStandard = href;
    document.head.appendChild(link);
  }

  function loadScript(src) {
    if (document.querySelector(`script[data-portfolio-standard="${src}"]`)) return;
    const script = document.createElement('script');
    script.src = `${src}?v=${BUILD}`;
    script.defer = true;
    script.dataset.portfolioStandard = src;
    script.onerror = () => console.error(`No se pudo cargar el estándar ${src}`);
    document.body.appendChild(script);
  }

  loadStyle('css/project-card-standard.css');
  loadStyle('css/project-detail-standard.css');
  loadScript('js/project-card-standard.js');
  loadScript('js/project-detail-standard.js');
})();
