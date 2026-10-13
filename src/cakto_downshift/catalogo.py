"""Modelos Claude e preço por milhão de tokens (USD). Atualizar preço é PR; a data diz de quando é."""
import re
from dataclasses import dataclass

from cakto_downshift.classes import Tier

DATA_TABELA = "2026-10-12"


@dataclass(frozen=True)
class Modelo:
    id: str
    familia: str
    tier: Tier
    entrada: float
    saida: float
    cache_leitura: float
    cache_escrita: float


MODELOS: tuple[Modelo, ...] = (
    Modelo("claude-haiku-5-5", "haiku", Tier.HAIKU, 0.10, 0.50, 0.01, 0.125),
    Modelo("claude-sonnet-5-5", "sonnet", Tier.SONNET, 2.0, 10.0, 0.20, 2.50),
    Modelo("claude-opus-5-5", "opus", Tier.OPUS, 4.0, 20.0, 0.40, 5.00),
    Modelo("claude-fable-5-1", "fable", Tier.FABLE, 10.0, 50.0, 1.00, 12.50),
)

_FAMILIA = re.compile(r"(haiku|sonnet|opus|fable)")


def familia_de(modelo: str | None) -> str | None:
    """"claude-opus-5-5-20260301", "opus[1m]" e "opus" são a mesma família para o Claude Code."""
    if not modelo:
        return None
    achado = _FAMILIA.search(modelo.lower())
    return achado.group(1) if achado else None


def por_familia(familia: str) -> Modelo | None:
    return next((m for m in MODELOS if m.familia == familia), None)


def custo_usd(m: Modelo, entrada: int, saida: int, cache_leitura: int = 0, cache_escrita: int = 0) -> float:
    por_milhao = 1_000_000
    return (entrada * m.entrada + saida * m.saida + cache_leitura * m.cache_leitura + cache_escrita * m.cache_escrita) / por_milhao
