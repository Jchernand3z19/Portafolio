import pytest

from precios_supermercados.automation.la_colonia_dispatcher import evaluate_event


def event(body, *, authorized=True, is_pr=True):
    user = {
        "login": "Jchernand3z19" if authorized else "externo",
        "id": 143058181 if authorized else 999,
        "type": "User",
    }
    return {
        "repository": {"full_name": "Jchernand3z19/Portafolio"},
        "issue": {"pull_request": {"url": "x"}} if is_pr else {},
        "comment": {
            "id": 77,
            "body": body,
            "user": user,
            "author_association": "OWNER" if authorized else "NONE",
        },
    }


def pr(*, fork=False, state="open"):
    return {
        "state": state,
        "base": {"repo": {"full_name": "Jchernand3z19/Portafolio"}},
        "head": {
            "ref": "feature/la-colonia-full-crawl-validation",
            "repo": {
                "full_name": "otro/fork" if fork else "Jchernand3z19/Portafolio",
                "fork": fork,
            },
        },
    }


def decide(command, **kwargs):
    return evaluate_event(event(command, **kwargs), pr())


@pytest.mark.parametrize("size", [10, 20, 30, 50])
def test_smoke_valido(size):
    decision = decide(f"/run-la-colonia smoke page_size={size}")
    assert decision.accepted
    assert decision.inputs["page_size"] == str(size)
    assert decision.inputs["max_pages"] == "2"
    assert decision.inputs["allow_full"] is False


def test_page_size_invalido():
    assert not decide("/run-la-colonia smoke page_size=40").accepted


def test_comando_incompleto():
    assert not decide("/run-la-colonia smoke").accepted


def test_argumento_desconocido():
    assert not decide("/run-la-colonia smoke page_size=10 extra=1").accepted


def test_full_rechazado():
    assert not decide("/run-la-colonia full page_size=10").accepted


def test_allow_full_rechazado():
    assert not decide("/run-la-colonia smoke page_size=10 allow_full=true").accepted


def test_autor_no_autorizado():
    decision = evaluate_event(event("/run-la-colonia smoke page_size=10", authorized=False), pr())
    assert not decision.accepted
    assert "Autor" in decision.reason


def test_comentario_no_pertenece_a_pr():
    decision = evaluate_event(event("/run-la-colonia smoke page_size=10", is_pr=False), None)
    assert not decision.accepted
    assert not decision.should_comment


def test_pr_de_fork():
    decision = evaluate_event(event("/run-la-colonia smoke page_size=10"), pr(fork=True))
    assert not decision.accepted


def test_staged_con_max_pages():
    decision = decide("/run-la-colonia staged page_size=20 max_pages=10 profile=baseline")
    assert decision.accepted
    assert decision.inputs["max_pages"] == "10"
    assert decision.inputs["max_products"] == "0"


def test_staged_con_max_products():
    decision = decide("/run-la-colonia staged page_size=20 max_products=100 profile=baseline")
    assert decision.accepted
    assert decision.inputs["max_products"] == "100"


def test_ambos_limites_presentes():
    command = "/run-la-colonia staged page_size=20 max_pages=5 max_products=100 profile=baseline"
    assert not decide(command).accepted


def test_ningun_limite_presente():
    assert not decide("/run-la-colonia staged page_size=20 profile=baseline").accepted


def test_max_products_no_divisible():
    command = "/run-la-colonia staged page_size=30 max_products=100 profile=baseline"
    assert not decide(command).accepted


def test_validation_sin_umbrales():
    command = "/run-la-colonia staged page_size=20 max_products=100 profile=validation"
    assert not decide(command).accepted


def test_validation_con_umbrales_validos():
    command = (
        "/run-la-colonia staged page_size=20 max_products=100 profile=validation "
        "max_missing_price_ratio=0.05 max_duplicate_sku_ratio=0.01 "
        "max_duplicate_product_ratio=0.01 max_total_change_ratio=0.005"
    )
    decision = decide(command)
    assert decision.accepted
    assert decision.inputs["max_total_change_ratio"] == "0.005"


def test_umbral_fuera_de_rango():
    command = (
        "/run-la-colonia staged page_size=20 max_products=100 profile=validation "
        "max_missing_price_ratio=1.1 max_duplicate_sku_ratio=0.01 "
        "max_duplicate_product_ratio=0.01 max_total_change_ratio=0.005"
    )
    assert not decide(command).accepted


def test_intento_inyeccion_shell():
    command = "/run-la-colonia smoke page_size=10;curl=evil"
    decision = decide(command)
    assert not decision.accepted
    assert decision.inputs is None
