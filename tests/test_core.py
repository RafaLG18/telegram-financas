from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from caderneta.core import (
    CATEGORIAS_PADRAO,
    ValorInvalidoError,
    achar_categoria_por_nome,
    desfazer_ultima,
    intervalo_do_mes,
    listar_categorias,
    registrar_transacao,
    resumo,
    seed_categorias,
)
from caderneta.models import ENTRADA, GASTO

HOJE = dt.date(2026, 8, 18)


def test_seed_e_idempotente(sessao: Session) -> None:
    assert seed_categorias(sessao) == len(CATEGORIAS_PADRAO)
    assert seed_categorias(sessao) == 0
    assert len(listar_categorias(sessao)) == len(CATEGORIAS_PADRAO)


def test_listar_categorias_filtra_por_tipo(sessao: Session) -> None:
    seed_categorias(sessao)
    nomes = {c.nome for c in listar_categorias(sessao, tipo=ENTRADA)}
    assert "Salário" in nomes
    assert "Mercado" not in nomes
    # 'Outros' e tipo AMBOS: aparece nos dois.
    assert "Outros" in nomes


def test_achar_categoria_por_prefixo(sessao: Session) -> None:
    seed_categorias(sessao)
    assert achar_categoria_por_nome(sessao, "merc").nome == "Mercado"
    assert achar_categoria_por_nome(sessao, "MERCADO").nome == "Mercado"
    assert achar_categoria_por_nome(sessao, "xyz") is None


def test_prefixo_ambiguo_nao_chuta(sessao: Session) -> None:
    seed_categorias(sessao)
    # "Salário" e "Saúde" comecam com "sa": ambiguo, melhor nao adivinhar.
    assert achar_categoria_por_nome(sessao, "sa") is None


def test_registrar_transacao(sessao: Session) -> None:
    t, criada = registrar_transacao(
        sessao, tipo=GASTO, valor_centavos=5000, data=HOJE, descricao="pão"
    )
    assert criada is True
    assert t.id is not None
    assert t.valor_centavos == 5000


def test_valor_zero_ou_negativo_e_rejeitado(sessao: Session) -> None:
    with pytest.raises(ValorInvalidoError):
        registrar_transacao(sessao, tipo=GASTO, valor_centavos=0, data=HOJE)
    with pytest.raises(ValorInvalidoError):
        registrar_transacao(sessao, tipo=GASTO, valor_centavos=-1, data=HOJE)


def test_mesmo_update_id_nao_duplica(sessao: Session) -> None:
    """Telegram reenvia updates. Sem isso, um gasto vira dois."""
    primeira, criada1 = registrar_transacao(
        sessao, tipo=GASTO, valor_centavos=5000, data=HOJE, origem_update_id=999
    )
    segunda, criada2 = registrar_transacao(
        sessao, tipo=GASTO, valor_centavos=5000, data=HOJE, origem_update_id=999
    )
    assert criada1 is True
    assert criada2 is False
    assert primeira.id == segunda.id
    assert resumo(sessao, HOJE, HOJE).total_gasto == 5000


def test_update_id_nulo_nao_bloqueia_repetidos(sessao: Session) -> None:
    # Dois cafés de R$ 5 no mesmo dia sao dois lancamentos legitimos.
    registrar_transacao(sessao, tipo=GASTO, valor_centavos=500, data=HOJE)
    registrar_transacao(sessao, tipo=GASTO, valor_centavos=500, data=HOJE)
    assert resumo(sessao, HOJE, HOJE).total_gasto == 1000


def test_resumo_saldo_e_categorias(sessao: Session) -> None:
    seed_categorias(sessao)
    mercado = achar_categoria_por_nome(sessao, "Mercado")
    salario = achar_categoria_por_nome(sessao, "Salário")

    registrar_transacao(
        sessao, tipo=ENTRADA, valor_centavos=300000, data=HOJE,
        categoria_id=salario.id,
    )
    registrar_transacao(
        sessao, tipo=GASTO, valor_centavos=5000, data=HOJE, categoria_id=mercado.id
    )
    registrar_transacao(
        sessao, tipo=GASTO, valor_centavos=2500, data=HOJE, categoria_id=mercado.id
    )

    r = resumo(sessao, HOJE, HOJE)
    assert r.total_entrada == 300000
    assert r.total_gasto == 7500
    assert r.saldo == 292500
    assert len(r.gastos_por_categoria) == 1
    assert r.gastos_por_categoria[0].nome == "Mercado"
    assert r.gastos_por_categoria[0].quantidade == 2


def test_resumo_respeita_o_intervalo(sessao: Session) -> None:
    registrar_transacao(sessao, tipo=GASTO, valor_centavos=1000, data=HOJE)
    registrar_transacao(
        sessao, tipo=GASTO, valor_centavos=9999, data=dt.date(2026, 7, 31)
    )
    inicio, fim = intervalo_do_mes(HOJE)
    assert resumo(sessao, inicio, fim).total_gasto == 1000


def test_resumo_vazio(sessao: Session) -> None:
    r = resumo(sessao, HOJE, HOJE)
    assert r.vazio is True
    assert r.saldo == 0


@pytest.mark.parametrize(
    ("dia", "esperado"),
    [
        (dt.date(2026, 8, 18), (dt.date(2026, 8, 1), dt.date(2026, 8, 31))),
        (dt.date(2026, 2, 10), (dt.date(2026, 2, 1), dt.date(2026, 2, 28))),
        (dt.date(2024, 2, 10), (dt.date(2024, 2, 1), dt.date(2024, 2, 29))),
        (dt.date(2026, 12, 5), (dt.date(2026, 12, 1), dt.date(2026, 12, 31))),
    ],
)
def test_intervalo_do_mes(dia: dt.date, esperado: tuple[dt.date, dt.date]) -> None:
    assert intervalo_do_mes(dia) == esperado


def test_desfazer_remove_o_ultimo(sessao: Session) -> None:
    seed_categorias(sessao)
    mercado = achar_categoria_por_nome(sessao, "Mercado")
    registrar_transacao(sessao, tipo=GASTO, valor_centavos=1000, data=HOJE)
    registrar_transacao(
        sessao, tipo=GASTO, valor_centavos=2000, data=HOJE, categoria_id=mercado.id
    )

    removida = desfazer_ultima(sessao)
    assert removida is not None
    assert removida.valor_centavos == 2000
    assert removida.categoria == "Mercado"
    assert resumo(sessao, HOJE, HOJE).total_gasto == 1000


def test_desfazer_sem_nada(sessao: Session) -> None:
    assert desfazer_ultima(sessao) is None
