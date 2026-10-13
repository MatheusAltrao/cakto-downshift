import pytest

from cakto_downshift.catalogo import MODELOS, custo_usd, familia_de, por_familia
from cakto_downshift.classes import Tier


@pytest.mark.parametrize("entrada,esperado", [
    ("claude-opus-5-5", "opus"),
    ("claude-opus-5-5-20260301", "opus"),
    ("opus[1m]", "opus"),
    ("opus", "opus"),
    ("claude-haiku-5-5", "haiku"),
    ("claude-fable-5-1", "fable"),
    ("gpt-6-sol", None),
    ("", None),
    (None, None),
])
def test_familia_de(entrada, esperado):
    assert familia_de(entrada) == esperado


def test_catalogo_tem_as_quatro_familias_com_tier():
    assert {m.familia: m.tier for m in MODELOS} == {
        "haiku": Tier.HAIKU, "sonnet": Tier.SONNET, "opus": Tier.OPUS, "fable": Tier.FABLE,
    }


def test_custo_por_milhao():
    opus = por_familia("opus")
    assert custo_usd(opus, entrada=1_000_000, saida=0) == pytest.approx(opus.entrada)
    assert custo_usd(opus, entrada=0, saida=0, cache_leitura=2_000_000) == pytest.approx(2 * opus.cache_leitura)
