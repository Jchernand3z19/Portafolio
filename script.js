(() => {
  const BUILD = '20260904-six-chain-coverage-v1';

  function loadStandards(attempt = 0) {
    const projectsReady = Boolean(
      document.querySelector('#proyectos .price-card') &&
      document.querySelector('#proyectos .mw-card')
    );

    if (!projectsReady && attempt < 200) {
      window.setTimeout(() => loadStandards(attempt + 1), 25);
      return;
    }

    const standards = document.createElement('script');
    standards.src = `js/portfolio-standards-loader.js?v=${BUILD}`;
    standards.defer = true;
    standards.onerror = () => {
      console.error('No se pudieron cargar los estándares visuales del portafolio.');
    };
    document.body.appendChild(standards);
  }

  const entrypoint = document.createElement('script');
  entrypoint.src = `js/main.js?v=${BUILD}`;
  entrypoint.defer = true;
  entrypoint.onload = () => loadStandards();
  entrypoint.onerror = () => {
    console.error('No se pudo cargar la aplicación principal del portafolio.');
  };
  document.body.appendChild(entrypoint);
})();