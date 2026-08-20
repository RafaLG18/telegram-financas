"""Parsing de texto livre: valor, data e descricao.

Sem LLM: regra explicita, deterministica e testavel. O fluxo guiado continua
sendo o caminho principal; isto aqui e o atalho para o uso diario.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_SO_NUMERO = re.compile(r"\d[\d.,]*")
_DATA_BR = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")


def parse_valor(texto: str) -> int | None:
    """Converte '50', '50,90', 'R$ 1.250,00' em centavos. None se nao for valor."""
    t = texto.strip().lower().replace("r$", "").replace(" ", "")
    if not t or not _SO_NUMERO.fullmatch(t):
        return None

    tem_virgula, tem_ponto = "," in t, "." in t

    if tem_virgula and tem_ponto:
        # O separador mais a direita e o decimal.
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif tem_virgula:
        if t.count(",") > 1:
            return None
        t = t.replace(",", ".")
    elif tem_ponto:
        partes = t.split(".")
        decimal_simples = len(partes) == 2 and len(partes[1]) in (1, 2)
        if not decimal_simples:
            # So aceita como separador de milhar se todos os grupos tiverem 3 digitos.
            if not all(len(p) == 3 for p in partes[1:]):
                return None
            t = t.replace(".", "")

    try:
        valor = Decimal(t)
    except InvalidOperation:
        return None

    if valor <= 0:
        return None

    centavos = int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return centavos or None


def parse_data(texto: str, hoje: dt.date) -> tuple[dt.date | None, str]:
    """Extrai data relativa ou dd/mm do texto. Devolve (data, texto_sem_a_data)."""
    t = texto.strip()
    baixo = t.lower()

    for termo, delta in (("anteontem", 2), ("ontem", 1), ("hoje", 0)):
        if re.search(rf"\b{termo}\b", baixo):
            limpo = re.sub(rf"\b{termo}\b", " ", baixo, count=1)
            return hoje - dt.timedelta(days=delta), " ".join(limpo.split())

    achado = _DATA_BR.search(t)
    if achado:
        dia, mes, ano = achado.group(1), achado.group(2), achado.group(3)
        try:
            if ano is None:
                candidata = dt.date(hoje.year, int(mes), int(dia))
                # 31/12 lancado em 02/01 quase certamente e do ano passado.
                if (candidata - hoje).days > 180:
                    candidata = candidata.replace(year=hoje.year - 1)
            else:
                a = int(ano)
                candidata = dt.date(2000 + a if a < 100 else a, int(mes), int(dia))
        except ValueError:
            return None, t
        limpo = (t[: achado.start()] + " " + t[achado.end() :]).strip()
        return candidata, " ".join(limpo.split())

    return None, t


# Passado esse limite a data ainda vale, mas merece um aviso na previa: errar o
# ano em `15/08/2015` e facil demais para aceitar calado.
DIAS_DATA_ANTIGA = 730

DATA_OK = "ok"
DATA_NAO_ENTENDI = "nao_entendi"
DATA_FUTURA = "futura"


@dataclass(frozen=True)
class DataLivre:
    """Resultado de `parse_data_estrita`. `data` so vem preenchida se motivo=OK."""

    data: dt.date | None
    motivo: str


def parse_data_estrita(texto: str, hoje: dt.date) -> DataLivre:
    """Le uma mensagem que deve ser *inteira* uma data.

    Diferente de `parse_data`, que garimpa a data no meio de uma frase, aqui
    sobra de texto e erro: quem digita no estado de data nao esta descrevendo o
    gasto. O motivo volta junto porque o handler precisa dizer coisas diferentes
    para "nao entendi" e para "isso e no futuro".
    """
    t = texto.strip()
    if not t:
        return DataLivre(None, DATA_NAO_ENTENDI)

    data, resto = parse_data(t, hoje)
    if data is None or resto:
        return DataLivre(None, DATA_NAO_ENTENDI)
    if data > hoje:
        return DataLivre(None, DATA_FUTURA)
    return DataLivre(data, DATA_OK)


@dataclass(frozen=True)
class EntradaRapida:
    valor_centavos: int
    descricao: str
    data: dt.date


def parse_lancamento(texto: str, hoje: dt.date) -> EntradaRapida | None:
    """'50 mercado', 'mercado 50', '1.250,00 aluguel ontem' -> EntradaRapida."""
    data, resto = parse_data(texto, hoje)
    tokens = resto.split()
    if not tokens:
        return None

    for i, token in enumerate(tokens):
        centavos = parse_valor(token)
        if centavos is not None:
            descricao = " ".join(tokens[:i] + tokens[i + 1 :]).strip()
            return EntradaRapida(centavos, descricao, data or hoje)

    return None


def formata_valor(centavos: int) -> str:
    inteiro, resto = divmod(abs(centavos), 100)
    milhar = f"{inteiro:,}".replace(",", ".")
    sinal = "-" if centavos < 0 else ""
    return f"{sinal}R$ {milhar},{resto:02d}"
