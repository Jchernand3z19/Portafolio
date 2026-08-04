(() => {
  const registeredProjects = new Set();

  function getGrid() {
    return document.querySelector('#proyectos .projects-grid');
  }

  function prepare() {
    const grid = getGrid();
    if (!grid || grid.dataset.registryReady === 'true') return grid;

    grid.replaceChildren();
    grid.dataset.registryReady = 'true';
    return grid;
  }

  function register({ id, cardHtml, detailHtml = '', setup }) {
    if (!id || registeredProjects.has(id)) return false;

    const grid = prepare();
    if (!grid) return false;

    const cardTemplate = document.createElement('template');
    cardTemplate.innerHTML = String(cardHtml || '').trim();
    const card = cardTemplate.content.firstElementChild;
    if (!card) throw new Error(`El proyecto ${id} no contiene una tarjeta válida.`);

    card.dataset.portfolioProject = id;
    grid.appendChild(card);

    let detail = null;
    if (detailHtml) {
      const detailTemplate = document.createElement('template');
      detailTemplate.innerHTML = String(detailHtml).trim();
      detail = detailTemplate.content.firstElementChild;
      if (detail) {
        detail.dataset.portfolioProject = id;
        document.body.appendChild(detail);
      }
    }

    registeredProjects.add(id);
    if (typeof setup === 'function') setup({ card, detail });
    return true;
  }

  window.PortfolioProjects = Object.freeze({
    prepare,
    register,
    has: id => registeredProjects.has(id),
    list: () => Array.from(registeredProjects)
  });
})();
