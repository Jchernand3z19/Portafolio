(() => {
  const BUILD = '20260904-six-chain-coverage-v1';
  const entrypoint = document.createElement('script');
  entrypoint.src = `js/main.js?v=${BUILD}`;
  entrypoint.defer = true;
  entrypoint.onload = () => {
    const standards = document.createElement('script');
    standards.src = `js/portfolio-standards-loader.js?v=${BUILD}`;
    standards.defer = true;
    standards.onerror = () => {
      console.error('No se pudieron cargar los estándares visuales del portafolio.');
    };
    document.body.appendChild(standards);
  };
  entrypoint.onerror = () => {
    console.error('No se pudo cargar la aplicación principal del portafolio.');
  };
  document.body.appendChild(entrypoint);
})();