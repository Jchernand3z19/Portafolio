# Estructura del repositorio

## Objetivo

Mantener el portafolio preparado para crecer sin mezclar código, datos, automatizaciones ni documentación entre proyectos.

## Decisión de arquitectura

El sitio publicado permanece en la raíz porque GitHub Pages utiliza esa ubicación. Los proyectos técnicos se almacenan como carpetas hermanas independientes.

```text
Portafolio/
├── index.html
├── css/
├── script.js
├── project-registry.js
├── project-<slug>.js
├── project-<slug>.css
├── assets/
│   ├── mundial/
│   ├── code/
│   └── projects/
│       └── <slug>/
├── mundial-2026-predicciones/
├── <nuevo-proyecto>/
├── docs/
├── PROJECT_TEMPLATE.md
└── .github/workflows/
```

## Qué pertenece a la raíz

La raíz contiene únicamente archivos necesarios para publicar y administrar el portafolio:

- Página HTML principal.
- Estilos y comportamiento general.
- Registro y módulos visuales de los proyectos.
- Recursos que el navegador necesita cargar.
- Documentación general del repositorio.

No debe utilizarse como carpeta de trabajo para archivos temporales, notebooks sueltos, exportaciones o datasets completos.

## Qué pertenece a cada proyecto

Cada proyecto técnico debe tener su propia carpeta:

```text
<slug-del-proyecto>/
├── README.md
├── requirements.txt       # Cuando utiliza Python
├── .env.example           # Solo nombres y valores de ejemplo
├── src/                   # Código reutilizable
├── scripts/               # Procesos ejecutables
├── notebooks/             # Solo si aportan al proyecto
├── data/
│   ├── samples/           # Datos pequeños y públicos
│   └── README.md          # Origen y restricciones de los datos
├── dashboard/             # PBIX, Looker, Apps Script u otros recursos
├── docs/                  # Arquitectura y decisiones propias
└── tests/                 # Validaciones automatizadas
```

No todas las carpetas son obligatorias. Deben crearse solo cuando tengan contenido real.

## Convención de nombres

Usar minúsculas y guiones:

```text
mundial-2026-predicciones
precios-supermercados-sps
automatizacion-reportes-comerciales
```

Evitar nombres como:

```text
proyecto-nuevo
prueba-final
version-2
carpeta-juan
```

El nombre debe explicar el problema o producto analítico.

## Publicación de proyectos en el sitio

Cada proyecto visible utiliza dos recursos independientes:

```text
project-<slug>.js
project-<slug>.css
```

El JavaScript genera:

- Tarjeta del proyecto.
- Vista detallada.
- Eventos y navegación propios.

El módulo debe registrarse con `project-registry.js`:

```javascript
window.PortfolioProjects.register({
  id: 'mi-proyecto',
  cardHtml: card(),
  detailHtml: detail(),
  setup: setupProject
});
```

Después se agrega a las listas de `script.js`:

```javascript
const projectStyles = [
  'project-mundial.css',
  'project-mi-proyecto.css'
];

const projectModules = [
  'project-mundial.js',
  'project-mi-proyecto.js'
];
```

Esta estructura evita que un módulo use `innerHTML` para eliminar las tarjetas de los demás.

## Recursos visuales

Los recursos nuevos deben ubicarse en:

```text
assets/projects/<slug>/
```

Ejemplo:

```text
assets/projects/precios-supermercados-sps/portada.webp
assets/projects/precios-supermercados-sps/dashboard-01.webp
assets/projects/precios-supermercados-sps/arquitectura.svg
```

Los recursos heredados del Mundial permanecen en `assets/mundial/` para conservar las rutas ya publicadas.

## Automatizaciones

Cada proyecto debe tener un workflow separado:

```text
.github/workflows/<slug>.yml
```

Un workflow debe:

- Definir su `working-directory`.
- Instalar únicamente sus dependencias.
- Referenciar secretos por nombre.
- Validar los archivos requeridos antes de ejecutar.
- No imprimir llaves privadas ni tokens.

## Documentación mínima

Cada README de proyecto debe responder:

1. ¿Qué problema resuelve?
2. ¿Quién utilizaría el resultado?
3. ¿Qué fuentes utiliza?
4. ¿Cómo transforma los datos?
5. ¿Qué métricas o salidas genera?
6. ¿Cómo se ejecuta?
7. ¿Qué información sensible fue excluida?
8. ¿Cuál es su estado actual?

## Reglas para datos y secretos

- No confirmar `.env`, cuentas de servicio, tokens ni contraseñas.
- No publicar información empresarial o personal sin autorización.
- Preferir datos de muestra pequeños.
- Documentar el origen y la fecha de actualización.
- Usar GitHub Secrets para automatizaciones.
- Incluir `.env.example` sin valores reales.

## Flujo para crear el siguiente proyecto

1. Copiar la estructura de `PROJECT_TEMPLATE.md`.
2. Crear una carpeta hermana de `mundial-2026-predicciones/`.
3. Desarrollar y documentar el proyecto dentro de esa carpeta.
4. Crear recursos en `assets/projects/<slug>/`.
5. Crear `project-<slug>.js` y `project-<slug>.css`.
6. Registrar el módulo en `script.js`.
7. Crear un workflow separado cuando necesite automatización.
8. Verificar enlaces, vista móvil, datos sensibles y README.

## Estado de proyectos

Solo deben mostrarse en la página proyectos que tengan al menos:

- Descripción completa.
- Evidencia visual o dashboard.
- Código o explicación técnica verificable.
- Enlaces funcionales.

Los proyectos incompletos pueden permanecer en una rama de trabajo, pero no deben aparecer como tarjetas activas en el portafolio principal.
