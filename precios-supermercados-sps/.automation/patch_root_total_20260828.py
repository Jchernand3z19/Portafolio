from pathlib import Path

path = Path("scripts/obtener_catalogo_sps_la_colonia_operativo.py")
text = path.read_text(encoding="utf-8")

anchor = "\n\ndef _run_catalog(*, page_size: int, delay_seconds: float) -> dict[str, Any]:\n"
helper = '''

def _resolve_root_total_after_partitions(
    *,
    context: Any,
    root_url: str,
    initial_total: int,
    unique_product_count: int,
    diagnostic: dict[str, Any],
) -> int:
    """Relee una sola vez el total raíz si el binding inicial quedó transitorio.

    Sólo corrige el total cuando las dos señales de partición ya coinciden
    exactamente con las identidades únicas extraídas. Cualquier otra discrepancia
    conserva el comportamiento fail-closed.
    """

    if unique_product_count == initial_total:
        return initial_total
    if (
        diagnostic["partition_quantity_estimate_sum"] != unique_product_count
        or diagnostic["partition_observed_total_sum"] != unique_product_count
    ):
        raise full.FullCatalogError(
            "unique_product_coverage_mismatch", diagnostic=diagnostic
        )

    _ensure_request_budget(diagnostic)
    response = context.request.get(
        root_url,
        timeout=core.PRODUCT_REQUEST_TIMEOUT_MS,
        fail_on_status_code=False,
    )
    payload = core._read_json_response(
        response, diagnostic, kind="root_product_search_recheck"
    )
    rechecked_total, _ = core._read_shape(payload)
    diagnostic["product_requests_completed"] += 1
    if rechecked_total <= 0 or rechecked_total != unique_product_count:
        raise full.FullCatalogError(
            "unique_product_coverage_mismatch", diagnostic=diagnostic
        )
    diagnostic["catalog_products_reported"] = rechecked_total
    return rechecked_total
'''

if "def _resolve_root_total_after_partitions(" not in text:
    if anchor not in text:
        raise SystemExit("run_catalog_anchor_missing")
    text = text.replace(anchor, helper + anchor, 1)

old = '''            if len(unique_products) != root_total:
                raise full.FullCatalogError(
                    "unique_product_coverage_mismatch", diagnostic=diagnostic
                )

            artifact = {
'''
new = '''            root_total = _resolve_root_total_after_partitions(
                context=context,
                root_url=root_url,
                initial_total=root_total,
                unique_product_count=len(unique_products),
                diagnostic=diagnostic,
            )

            artifact = {
'''

if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("coverage_block_missing")

path.write_text(text, encoding="utf-8")
