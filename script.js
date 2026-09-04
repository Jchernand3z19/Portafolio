(() => {
  const BUILD = '20260904-project-cards-v1';
  const entrypoint = document.createElement('script');
  entrypoint.src = `js/main.js?v=${BUILD}`;
  entrypoint.defer = true;
  entrypoint.onload = () => {
    const style = document.createElement('link');
    style.rel = 'stylesheet';
    style.href = `css/project-card-standard.css?v=${BUILD}`;
    document.head.appendChild(style);

    const standardizer = document.createElement('script');
    standardizer.src = `js/project-card-standard.js?v=${BUILD}`;
    standardizer.defer = true;
    standardizer.onerror = () => {
      console.error('No se pudo cargar el estándar visual de proyectos.');
    };
    document.body.appendChild(standardizer);
  };
  entrypoint.onerror = () => {
    console.error('No se pudo cargar la aplicación principal del portafolio.');
  };
  document.body.appendChild(entrypoint);
})();