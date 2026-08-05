"""Valida comandos cerrados para despachar recorridos live de La Colonia."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

AUTHORIZED_LOGIN = "Jchernand3z19"
AUTHORIZED_USER_ID = 143058181
AUTHORIZED_USER_TYPE = "User"
AUTHORIZED_ASSOCIATION = "OWNER"
EXPECTED_REPOSITORY = "Jchernand3z19/Portafolio"
COMMAND_PREFIX = "/run-la-colonia"
LIVE_WORKFLOW = ".github/workflows/precios-supermercados-sps-la-colonia-live.yml"
ALLOWED_PAGE_SIZES = {10, 20, 30, 50}
THRESHOLD_KEYS = (
    "max_missing_price_ratio",
    "max_duplicate_sku_ratio",
    "max_duplicate_product_ratio",
    "max_total_change_ratio",
)
TOKEN_RE = re.compile(r"(?P<key>[a-z_]+)=(?P<value>[A-Za-z0-9.]+)\Z")
DECIMAL_RE = re.compile(r"(?:0(?:\.\d+)?|1(?:\.0+)?)\Z")


@dataclass(frozen=True)
class DispatchDecision:
    accepted: bool
    should_comment: bool
    reason: str
    ref: str | None = None
    inputs: dict[str, Any] | None = None

    def as_dict(self, *, comment: str) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "should_comment": self.should_comment,
            "reason": self.reason,
            "ref": self.ref,
            "inputs": self.inputs,
            "workflow": LIVE_WORKFLOW,
            "comment": comment,
        }


def _rejected(reason: str, *, should_comment: bool = True) -> DispatchDecision:
    return DispatchDecision(False, should_comment, reason)


def _authorized(comment: Mapping[str, Any]) -> bool:
    user = comment.get("user")
    return (
        isinstance(user, Mapping)
        and user.get("login") == AUTHORIZED_LOGIN
        and user.get("id") == AUTHORIZED_USER_ID
        and user.get("type") == AUTHORIZED_USER_TYPE
        and comment.get("author_association") == AUTHORIZED_ASSOCIATION
    )


def _base_inputs(*, mode: str, page_size: int, profile: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "page_size": str(page_size),
        "max_pages": "0",
        "max_products": "0",
        "delay_seconds": "1.5",
        "profile": profile,
        "max_missing_price_ratio": "",
        "max_duplicate_sku_ratio": "",
        "max_duplicate_product_ratio": "",
        "max_total_change_ratio": "",
        "allow_full": False,
    }


def _parse_tokens(body: str) -> tuple[str, dict[str, str]] | DispatchDecision:
    if len(body) > 500 or "\n" in body or "\r" in body or "\t" in body:
        return _rejected("El comando debe ocupar una sola línea y usar únicamente la sintaxis permitida.")
    if body != body.strip() or "  " in body:
        return _rejected("El comando no coincide completamente con la sintaxis permitida.")

    parts = body.split(" ")
    if len(parts) < 2 or parts[0] != COMMAND_PREFIX:
        return _rejected("Comando incompleto.")
    mode = parts[1]
    if mode == "full":
        return _rejected("El modo full está prohibido en el despachador por comentarios.")
    if mode not in {"smoke", "staged"}:
        return _rejected("Modo no permitido.")

    parsed: dict[str, str] = {}
    for token in parts[2:]:
        match = TOKEN_RE.fullmatch(token)
        if not match:
            return _rejected("El comando contiene un argumento inválido o un intento de inyección.")
        key = match.group("key")
        if key in parsed:
            return _rejected(f"El argumento `{key}` está repetido.")
        parsed[key] = match.group("value")
    return mode, parsed


def _page_size(args: Mapping[str, str]) -> int | DispatchDecision:
    value = args.get("page_size")
    if value is None or not value.isdigit():
        return _rejected("`page_size` es obligatorio y debe ser entero.")
    page_size = int(value)
    if page_size not in ALLOWED_PAGE_SIZES:
        return _rejected("`page_size` debe ser 10, 20, 30 o 50.")
    return page_size


def _threshold(value: str, key: str) -> str | DispatchDecision:
    if not DECIMAL_RE.fullmatch(value):
        return _rejected(f"`{key}` debe ser un número decimal entre 0 y 1.")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return _rejected(f"`{key}` debe ser numérico.")
    if not Decimal("0") <= parsed <= Decimal("1"):
        return _rejected(f"`{key}` debe estar entre 0 y 1.")
    return value


def parse_command(body: str) -> DispatchDecision:
    """Interpreta solo las dos gramáticas autorizadas, sin ejecutar texto."""

    if not body.strip().startswith(COMMAND_PREFIX):
        return _rejected("Comentario ignorado: no contiene un comando de La Colonia.", should_comment=False)

    token_result = _parse_tokens(body)
    if isinstance(token_result, DispatchDecision):
        return token_result
    mode, args = token_result

    if "allow_full" in args:
        return _rejected("`allow_full` está prohibido en el despachador.")

    allowed = {"page_size"}
    if mode == "staged":
        allowed |= {"max_pages", "max_products", "profile", *THRESHOLD_KEYS}
    unknown = sorted(set(args) - allowed)
    if unknown:
        return _rejected(f"Argumento desconocido: `{unknown[0]}`.")

    page_size_result = _page_size(args)
    if isinstance(page_size_result, DispatchDecision):
        return page_size_result
    page_size = page_size_result

    if mode == "smoke":
        if set(args) != {"page_size"}:
            return _rejected("Smoke solo admite `page_size`; los demás valores son fijos.")
        inputs = _base_inputs(mode="smoke", page_size=page_size, profile="baseline")
        inputs["max_pages"] = "2"
        return DispatchDecision(True, True, "", inputs=inputs)

    profile = args.get("profile")
    if profile not in {"baseline", "validation"}:
        return _rejected("Staged requiere `profile=baseline` o `profile=validation`.")

    has_pages = "max_pages" in args
    has_products = "max_products" in args
    if has_pages == has_products:
        return _rejected("Staged requiere exactamente uno entre `max_pages` y `max_products`.")

    inputs = _base_inputs(mode="staged", page_size=page_size, profile=profile)
    if has_pages:
        value = args["max_pages"]
        if not value.isdigit() or not 1 <= int(value) <= 10:
            return _rejected("`max_pages` debe ser entero entre 1 y 10.")
        inputs["max_pages"] = value
    else:
        value = args["max_products"]
        if not value.isdigit() or not 100 <= int(value) <= 500:
            return _rejected("`max_products` debe ser entero entre 100 y 500.")
        if int(value) % page_size != 0:
            return _rejected("`max_products` debe ser múltiplo de `page_size`.")
        inputs["max_products"] = value

    present_thresholds = set(args).intersection(THRESHOLD_KEYS)
    if profile == "baseline":
        if present_thresholds:
            return _rejected("Baseline no admite umbrales.")
    else:
        if present_thresholds != set(THRESHOLD_KEYS):
            return _rejected("Validation exige los cuatro umbrales.")
        for key in THRESHOLD_KEYS:
            threshold_result = _threshold(args[key], key)
            if isinstance(threshold_result, DispatchDecision):
                return threshold_result
            inputs[key] = threshold_result

    return DispatchDecision(True, True, "", inputs=inputs)


def evaluate_event(event: Mapping[str, Any], pr: Mapping[str, Any] | None) -> DispatchDecision:
    """Aplica identidad, contexto de PR, repositorio y gramática cerrada."""

    repository = event.get("repository")
    if not isinstance(repository, Mapping) or repository.get("full_name") != EXPECTED_REPOSITORY:
        return _rejected("Repositorio no autorizado.", should_comment=False)

    issue = event.get("issue")
    if not isinstance(issue, Mapping) or not issue.get("pull_request"):
        return _rejected("El comentario no pertenece a un Pull Request.", should_comment=False)

    comment = event.get("comment")
    if not isinstance(comment, Mapping):
        return _rejected("Comentario inválido.", should_comment=False)
    body = comment.get("body")
    if not isinstance(body, str):
        return _rejected("Comentario inválido.", should_comment=False)
    wants_command = body.strip().startswith(COMMAND_PREFIX)

    if not _authorized(comment):
        return _rejected("Autor no autorizado.", should_comment=wants_command)
    if not isinstance(pr, Mapping):
        return _rejected("No fue posible verificar el Pull Request.", should_comment=wants_command)
    if pr.get("state") != "open":
        return _rejected("El Pull Request debe estar abierto.", should_comment=wants_command)

    base = pr.get("base")
    head = pr.get("head")
    base_repo = base.get("repo") if isinstance(base, Mapping) else None
    head_repo = head.get("repo") if isinstance(head, Mapping) else None
    if not isinstance(base_repo, Mapping) or base_repo.get("full_name") != EXPECTED_REPOSITORY:
        return _rejected("El Pull Request no pertenece a este repositorio.", should_comment=wants_command)
    if (
        not isinstance(head_repo, Mapping)
        or head_repo.get("full_name") != EXPECTED_REPOSITORY
        or bool(head_repo.get("fork"))
    ):
        return _rejected("Los Pull Requests provenientes de forks no están autorizados.", should_comment=wants_command)

    head_ref = head.get("ref") if isinstance(head, Mapping) else None
    if not isinstance(head_ref, str) or not head_ref:
        return _rejected("La rama head del Pull Request no es válida.", should_comment=wants_command)

    decision = parse_command(body)
    if not decision.accepted:
        return decision
    return DispatchDecision(True, True, "", ref=head_ref, inputs=decision.inputs)


def build_response_comment(
    decision: DispatchDecision,
    *,
    comment_id: int | str,
    dispatcher_run_id: int | str,
    dispatcher_url: str,
) -> str:
    """Construye una respuesta breve sin incluir texto no confiable."""

    marker = f"<!-- la-colonia-dispatch-request:{comment_id} -->"
    if not decision.accepted:
        return f"Comando rechazado: {decision.reason}\n\n{marker}"

    normalized = json.dumps(decision.inputs, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        "## Comando aceptado\n\n"
        f"- Workflow solicitado: `{LIVE_WORKFLOW}`\n"
        f"- Rama utilizada: `{decision.ref}`\n"
        f"- Run ID del despachador: `{dispatcher_run_id}`\n"
        f"- Enlace del despachador: {dispatcher_url}\n"
        "- Estado: **solicitud enviada**\n\n"
        "### Parámetros normalizados\n\n"
        f"```json\n{normalized}\n```\n\n"
        f"{marker}"
    )
