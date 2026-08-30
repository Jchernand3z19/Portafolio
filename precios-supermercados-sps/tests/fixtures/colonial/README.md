# Fixtures fuente Colonial

Capturadas con autorización humana de 24 horas el 2026-08-30. Bytes de respuesta
íntegros, sin imágenes descargadas ni cookies/headers privados.

- `products-40.json`: GET `https://supercolonial.com/products.json?limit=40&page=1`,
  2026-08-30T20:11:29Z, SHA256
  `31182c92da9e97605c4ed9e0db72847fd6618344514b94ffa7715af42bcb94b2`.
- `collection-section.html`: GET
  `https://supercolonial.com/collections/all?section_id=template--25869947109668__banner&limit=250&page=1`,
  2026-08-30T20:14:47Z, SHA256
  `e3ff4ecde53d98f08f4cfe4c7c245adc3fca797ef2878ee1ebb12409caf4e3cd`.

El query `limit=250` no cambia las 24 tarjetas de esta sección. No se lo interpreta
como capacidad soportada. El JSON sí permite 250 productos por página.
`available=true` de Shopify y el texto oculto «En stock» NO sustituyen el botón
visible: cuatro tarjetas de la sección están agotadas. Tests de escenarios
mutados usan copias sintéticas y no se presentan como observaciones reales.
