# PriceSmart — full restante detenido por ventana cruzada

La captura autorizada se detuvo después del primer POST. La consulta SPS
`S10D45`, `start=12`, `rows=200` recibió HTTP 200, `numFound=58` y 46 documentos,
pero repitió el producto `507265` de la muestra previa `start=0, rows=12`. La
unión produjo 57 identidades, una menos que el total declarado.

Esto demuestra que el orden de resultados cambió entre el probe y el full. Las
ventanas parciales tomadas en momentos distintos no pueden concatenarse sin
crear huecos, aunque `numFound` permanezca estable. La condición de detención se
aplicó antes de aceptar o pedir otra página.

```text
POST ejecutados                  1
HTTP 200                         1
retries                          0
documentos retornados           46
páginas aceptadas                0
Turso                             0
```

El request/response rechazado, ledger, hashes y script están en
[`raw-attempt.tar.gz`](raw-attempt.tar.gz), SHA-256
`08db4f1aa8ad5cd09db534c2f7f715d9d5b9bf6ea54f9af9a7d4601ac5aa58e6`.
El `auth_key` público se redactó; no hay cookies, `Authorization` ni credenciales.

## Replan fail-closed

El snapshot completo de Alimentos sí puede reutilizarse porque es una partición
cerrada dentro de una sola ejecución. Las páginas parciales del probe no se usarán
para completitud. El full revisado captura cada raíz restante desde `start=0`:

```text
SPS 6603 base                    25 POST
Florencia 6602 base              25 POST
base nuevo                       50 POST
intento ya consumido              1 POST
retries reservados                5 POST
máximo global revisado           56 POST
máximo adicional                 55 POST
documentos aceptados esperados 3,306
documentos ya descartados        46
máximo global retornado        3,352
```

Hogar y Moda usan offsets `0,200`; las otras 21 raíces no vacías usan sólo
`offset=0`. Audiología y Joyería siguen vacías. `rows=200`, concurrencia 1,
duración máxima 10 minutos, mismo endpoint y mismos dos clubes. Cualquier cambio
de `numFound`, repetición, hueco o bloqueo vuelve a detener el proceso.

El máximo anterior de 51 POST deja exactamente 50 intentos disponibles y no
permite conservar los cinco retries. Continuar requiere ampliar el máximo global
a 56 y el máximo de documentos retornados a 3,352. No se ejecutó esa continuación.

## Reproducción offline

```bash
python reports/pricesmart/2026-09-02-remaining-full-abort/verify.py
```

El verificador reproduce la colisión de identidad, demuestra la identidad
faltante y recalcula los offsets y el presupuesto desde la evidencia Discovery.
