(() => {
  const BUILD = '20260804-1714';
  const entrypoint = document.createElement('script');
  entrypoint.src = `js/main.js?v=${BUILD}`;
  entrypoint.defer = true;
  entrypoint.onerror = () => {
    console.error('No se pudo cargar la aplicación principal del portafolio.');
  };
  document.body.appendChild(entrypoint);
})();
