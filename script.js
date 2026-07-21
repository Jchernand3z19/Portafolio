"use strict";

    const menuToggle = document.getElementById("menu-toggle");
    const navLinks = document.getElementById("nav-links");
    const navAnchors = [...document.querySelectorAll(".nav__link")];
    const sections = [...document.querySelectorAll("[data-section]")];
    const projectView = document.getElementById("project-view");
    const projectClose = document.getElementById("project-close");
    const breadcrumbProjects = document.getElementById("breadcrumb-projects");
    let lastFocusedElement = null;

    const projectData = {
      mundial: {
        title: "Mundial 2026: análisis y predicción",
        tags: ["Python", "Google Sheets", "Apps Script", "Chart.js"],
        objective: "Centralizar información histórica de Copas del Mundo y presentar una predicción actualizable del torneo 2026 mediante una experiencia visual única.",
        previewLabel: "Dashboard histórico y predictivo",
        image: "assets/mundial-dashboard-preview.svg",
        imageAlt: "Dashboard Mundial 2026 con histórico, predicción inicial y predicción viva",
        process: [
          ["Integración de fuentes", "Se consolidaron tablas históricas, calendario, selecciones, jugadores y eventos del torneo."],
          ["Preparación y homologación", "Se limpiaron formatos y se normalizaron nombres para relacionar correctamente las distintas fuentes."],
          ["Modelo y predicción", "Python genera las tablas analíticas y las simulaciones utilizadas por la predicción inicial y viva."],
          ["Publicación interactiva", "Google Sheets y Apps Script entregan los datos a una interfaz desarrollada con HTML, CSS, JavaScript y Chart.js."]
        ],
        structure: `mundial-2026/
├── data/
│   ├── raw/
│   └── processed/
├── python/
│   ├── cleaning.py
│   └── prediction.py
├── apps-script/
│   ├── Code.gs
│   ├── index.html
│   ├── style.html
│   └── script.html
└── README.md`,
        code: `function updateDashboard(data) {
  renderHistoricalSummary(data);
  renderTeamAnalysis(data);
  renderInitialPrediction(data);
  renderLivePrediction(data);
}`,
        metrics: [
          ["448", "Partidos históricos integrados"],
          ["69", "Selecciones registradas"],
          ["7", "Torneos analizados"]
        ]
      },
      retail: {
        title: "Retail Sales Profitability Dashboard",
        tags: ["Google Sheets", "Apps Script", "JavaScript", "Chart.js"],
        objective: "Analizar el desempeño comercial desde una vista centralizada, relacionando ventas, rentabilidad, descuentos, envíos y productos con pérdidas.",
        previewLabel: "Dashboard de rentabilidad comercial",
        process: [
          ["Separación de datos", "Los datos originales se conservaron independientes de las tablas limpias y preparadas para análisis."],
          ["Creación de métricas", "Se calcularon margen, clasificación de descuentos, rentabilidad y tiempos de envío."],
          ["Análisis visual", "Se diseñaron indicadores y gráficos para detectar productos rentables, pérdidas y patrones comerciales."],
          ["Interacción", "Se incorporaron filtros y comportamientos dinámicos para explorar los resultados desde distintas perspectivas."]
        ],
        structure: `retail-profitability/
├── data/
│   ├── source/
│   └── clean/
├── apps-script/
│   ├── Code.gs
│   └── transforms.gs
├── web/
│   ├── index.html
│   ├── styles.css
│   └── dashboard.js
└── README.md`,
        code: `const profitMargin = revenue > 0
  ? ((revenue - cost) / revenue) * 100
  : 0;

const status = profitMargin < 0
  ? "Pérdida"
  : "Rentable";`,
        metrics: [
          ["Ventas", "Seguimiento del desempeño comercial"],
          ["Margen", "Análisis de rentabilidad y descuentos"],
          ["Envíos", "Evaluación de tiempos de entrega"]
        ]
      },
      automation: {
        title: "Automatización de reportes comerciales",
        tags: ["Oracle", "Correo", "Apps Script", "Google Sheets"],
        objective: "Reducir la intervención manual en la actualización de reportes comerciales mediante un flujo que recibe, procesa y publica información de forma programada.",
        previewLabel: "Flujo automatizado de reportería",
        process: [
          ["Recepción", "El reporte generado en Oracle llega automáticamente por correo en un formato definido."],
          ["Lectura y validación", "Apps Script identifica el archivo, valida su estructura y prepara la información para procesamiento."],
          ["Transformación", "Los datos se limpian, se homologan y se cargan en una base organizada en Google Sheets."],
          ["Actualización", "Los dashboards consultan la base procesada y muestran información actualizada durante el día."]
        ],
        structure: `report-automation/
├── oracle/
│   └── report-definition.md
├── apps-script/
│   ├── mail-reader.gs
│   ├── validator.gs
│   ├── transformer.gs
│   └── loader.gs
├── sheets/
│   └── data-model.md
└── README.md`,
        code: `function processLatestReport() {
  const file = findLatestAttachment();
  validateStructure(file);
  const cleanData = transformRows(file);
  loadToReportingBase(cleanData);
}`,
        metrics: [
          ["1 h", "Frecuencia de actualización"],
          ["5", "Etapas integradas"],
          ["1", "Flujo centralizado"]
        ]
      }
    };

    function setMenuState(open) {
      navLinks.classList.toggle("is-open", open);
      menuToggle.setAttribute("aria-expanded", String(open));
      menuToggle.setAttribute("aria-label", open ? "Cerrar menú de navegación" : "Abrir menú de navegación");
    }

    menuToggle.addEventListener("click", () => {
      setMenuState(!navLinks.classList.contains("is-open"));
    });

    navAnchors.forEach((anchor) => {
      anchor.addEventListener("click", () => setMenuState(false));
    });

    document.addEventListener("click", (event) => {
      const clickedInsideNav = event.target.closest(".nav");
      if (!clickedInsideNav && navLinks.classList.contains("is-open")) {
        setMenuState(false);
      }
    });

    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });

    document.querySelectorAll(".fade-in").forEach((element) => revealObserver.observe(element));

    const sectionObserver = new IntersectionObserver((entries) => {
      const visibleEntries = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

      if (!visibleEntries.length) return;

      const activeId = visibleEntries[0].target.id;
      navAnchors.forEach((anchor) => {
        anchor.classList.toggle("is-active", anchor.getAttribute("href") === `#${activeId}`);
      });
    }, {
      rootMargin: "-30% 0px -55% 0px",
      threshold: [0.05, 0.25, 0.5]
    });

    sections.forEach((section) => sectionObserver.observe(section));

    function escapeText(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function openProject(projectKey, trigger) {
      const project = projectData[projectKey];
      if (!project) return;

      lastFocusedElement = trigger;
      document.getElementById("detail-title").textContent = project.title;
      document.getElementById("breadcrumb-current").textContent = project.title;
      document.getElementById("detail-objective").textContent = project.objective;
      const detailPreview = document.getElementById("detail-preview");
      const detailPreviewImage = document.getElementById("detail-preview-image");
      const detailPreviewPlaceholder = document.getElementById("detail-preview-placeholder");
      document.getElementById("detail-preview-label").textContent = project.previewLabel;

      if (project.image) {
        detailPreviewImage.src = project.image;
        detailPreviewImage.alt = project.imageAlt || project.title;
        detailPreviewImage.hidden = false;
        detailPreviewPlaceholder.hidden = true;
        detailPreview.classList.add("has-image");
      } else {
        detailPreviewImage.removeAttribute("src");
        detailPreviewImage.alt = "";
        detailPreviewImage.hidden = true;
        detailPreviewPlaceholder.hidden = false;
        detailPreview.classList.remove("has-image");
      }

      document.getElementById("detail-structure").textContent = project.structure;
      document.getElementById("detail-code").textContent = project.code;

      document.getElementById("detail-tags").innerHTML = project.tags
        .map((tag) => `<span class="tag">${escapeText(tag)}</span>`)
        .join("");

      document.getElementById("detail-process").innerHTML = project.process
        .map(([title, description]) => `<li><strong>${escapeText(title)}</strong><span>${escapeText(description)}</span></li>`)
        .join("");

      document.getElementById("detail-metrics").innerHTML = project.metrics
        .map(([value, label]) => `
          <article class="metric">
            <span class="metric__value">${escapeText(value)}</span>
            <span class="metric__label">${escapeText(label)}</span>
          </article>
        `)
        .join("");

      projectView.hidden = false;
      document.body.classList.add("is-locked");
      projectView.scrollTop = 0;
      projectClose.focus();
    }

    function closeProject() {
      projectView.hidden = true;
      document.body.classList.remove("is-locked");
      if (lastFocusedElement) lastFocusedElement.focus();
    }

    document.querySelectorAll(".project-detail-trigger").forEach((trigger) => {
      trigger.addEventListener("click", () => openProject(trigger.dataset.project, trigger));
    });

    projectClose.addEventListener("click", closeProject);
    breadcrumbProjects.addEventListener("click", closeProject);

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !projectView.hidden) {
        closeProject();
      }
    });
