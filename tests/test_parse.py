from __future__ import annotations

import datetime as dt

import pytest

from caderneta.parse import (
    formata_valor,
    parse_data,
    parse_lancamento,
    parse_valor,
)

HOJE = dt.date(2026, 8, 18)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("50", 5000),
        ("50,90", 5090),
        ("50.90", 5090),
        ("50,9", 5090),
        ("R$ 50", 5000),
        ("r$50,00", 5000),
        ("1.250,00", 125000),
        ("1250", 125000),
        ("1.250", 125000),
        ("0,01", 1),
        ("1.234.567,89", 123456789),
    ],
)
def test_parse_valor_formatos_aceitos(texto: str, esperado: int) -> None:
    assert parse_valor(texto) == esperado


@pytest.mark.parametrize(
    "texto", ["", "mercado", "0", "0,00", "-50", "50,00,00", "1.2345", "abc50"]
)
def test_parse_valor_rejeita(texto: str) -> None:
    assert parse_valor(texto) is None


def test_ponto_ambiguo_resolve_pelo_tamanho_do_grupo() -> None:
    # Grupo de 3 digitos = milhar; grupo de 1-2 = decimal.
    assert parse_valor("1.250") == 125000
    assert parse_valor("50.90") == 5090
    assert parse_valor("1.25") == 125


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("ontem", dt.date(2026, 8, 17)),
        ("anteontem", dt.date(2026, 8, 16)),
        ("hoje", HOJE),
        ("15/08", dt.date(2026, 8, 15)),
        ("15/08/2025", dt.date(2025, 8, 15)),
    ],
)
def test_parse_data(texto: str, esperado: dt.date) -> None:
    data, _ = parse_data(f"mercado {texto}", HOJE)
    assert data == esperado


def test_data_futura_distante_vira_ano_passado() -> None:
    # Em agosto, "31/12" sem ano e do ano corrente, mas "01/01" ja passou.
    data, _ = parse_data("31/12", HOJE)
    assert data == dt.date(2026, 12, 31)


def test_data_invalida_nao_quebra() -> None:
    data, resto = parse_data("32/13", HOJE)
    assert data is None
    assert "32/13" in resto


def test_parse_lancamento_valor_primeiro() -> None:
    r = parse_lancamento("50 mercado", HOJE)
    assert r is not None
    assert r.valor_centavos == 5000
    assert r.descricao == "mercado"
    assert r.data == HOJE


def test_parse_lancamento_valor_no_fim() -> None:
    r = parse_lancamento("mercado 50", HOJE)
    assert r is not None
    assert r.valor_centavos == 5000
    assert r.descricao == "mercado"


def test_parse_lancamento_com_data_relativa() -> None:
    r = parse_lancamento("1.250,00 aluguel ontem", HOJE)
    assert r is not None
    assert r.valor_centavos == 125000
    assert r.descricao == "aluguel"
    assert r.data == dt.date(2026, 8, 17)


def test_parse_lancamento_sem_valor() -> None:
    assert parse_lancamento("bom dia", HOJE) is None


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (5000, "R$ 50,00"),
        (5090, "R$ 50,90"),
        (1, "R$ 0,01"),
        (125000, "R$ 1.250,00"),
        (-5000, "-R$ 50,00"),
        (0, "R$ 0,00"),
    ],
)
def test_formata_valor(centavos: int, esperado: str) -> None:
    assert formata_valor(centavos) == esperado
