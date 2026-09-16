# Estándar de identidad de producto v1

## Propósito

Este estándar separa el producto publicado por cada supermercado de la identidad
maestra usada para comparar precios. El título parecido nunca basta para declarar
que dos ofertas son el mismo producto.

## Entidades

- **Producto fuente:** fila preservada de `products`; mantiene nombre, marca,
  presentación, categoría, SKU/GTIN y demás evidencia tal como la reportó la
  fuente.
- **Perfil normalizado:** proyección reconstruible con marca, tipo, presentación,
  atributos y conflictos. No reemplaza el producto fuente.
- **Producto maestro:** identidad estable que puede reunir productos fuente sólo
  mediante `EXACT_TRADE_ITEM` o `VERIFIED_EQUIVALENT`.
- **Decisión:** relación auditada entre una pareja, ligada a las huellas de la
  evidencia que se revisó.

## Relaciones

| Relación | Significado | ¿Puede compartir precio comparado? |
| --- | --- | --- |
| `EXACT_TRADE_ITEM` | Mismo artículo comercial; GTIN válido común y sin contradicción material | Sí |
| `VERIFIED_EQUIVALENT` | Mismo artículo confirmado sin GTIN común disponible | Sólo después del gate de publicación |
| `PRODUCT_VARIANT` | Misma familia, pero cambia sabor, fórmula, talla, empaque u otro atributo material | No |
| `COMPARABLE_ALTERNATIVE` | Sustituto útil, no el mismo artículo | No como comparación exacta |
| `UNRESOLVED` | Evidencia insuficiente o revisión pendiente | No |
| `CONFLICT` | Existe una contradicción explícita | No |

## Orden de evidencia

1. GTIN válido común.
2. Catálogo del fabricante o marca.
3. Código de barras legible en el empaque.
4. Frente y reverso del empaque.
5. Página de detalle del supermercado.
6. Conversión explícita de unidades.
7. Título y campos del supermercado.

Imagen parecida, score textual o afirmación de IA sólo generan candidatos. No
confirman identidad por sí mismos.

## Reglas de decisión

1. Los datos fuente nunca se sobrescriben.
2. Dos GTIN válidos diferentes bloquean una identidad exacta.
3. Un conflicto explícito de marca, tipo, presentación, variante, sabor o empaque
   bloquea la unión. Un dato ausente no constituye conflicto.
4. `oz` no se convierte automáticamente a mililitros: debe demostrarse que el
   empaque declara `fl oz`.
5. Una equivalencia sin GTIN requiere decisión revisada, evidencia citada,
   producto maestro explícito y huellas vigentes de ambos registros.
6. Si cambia cualquiera de los registros fuente o la versión del motor, la
   decisión queda obsoleta y vuelve a `UNRESOLVED`.
7. La transitividad no se presume. Antes de formar un grupo, todas sus parejas
   materiales deben ser compatibles y estar respaldadas.
8. No puede haber dos productos fuente del mismo supermercado dentro de una
   identidad publicada sin resolver primero cuál variante/oferta representa.

## Casos iniciales

- **Nutri Yema 554 g vs 1.2 lb:** candidato fuerte, pero `UNRESOLVED` con los
  campos actualmente persistidos. Las cantidades difieren por aproximadamente
  1.8 % y una fuente omite la marca estructurada. Frente/reverso o código de
  barras deben confirmar la declaración comercial antes de aprobarlo.
- **Kraft Ranch Classic 8 oz vs 237 ml:** `UNRESOLVED`. La equivalencia numérica
  sólo es válida si `8 oz` significa `8 fl oz`, y `Classic` no puede ignorarse si
  el segundo producto declara otra variante.
- **Classic vs Light:** `CONFLICT`; no se fusiona aunque marca y contenido sean
  iguales.

## Despliegue

La versión v1 opera inicialmente en `shadow`: crea y valida decisiones privadas,
pero no cambia el catálogo B2C. Para habilitar publicación se exige un conjunto
de verdad base, precisión medida, cero regresiones críticas y una corrida shadow
sobre el catálogo completo.
