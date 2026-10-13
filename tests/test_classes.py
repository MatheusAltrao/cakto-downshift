from cakto_downshift.classes import FAMILIA_TIER, TIER_FAMILIA, Classe, Tier, tier_da_classe


def test_mapa_classe_tier():
    assert tier_da_classe(Classe.MECANICA) == Tier.HAIKU
    assert tier_da_classe(Classe.SIMPLES) == Tier.HAIKU
    assert tier_da_classe(Classe.MEDIA) == Tier.SONNET
    assert tier_da_classe(Classe.COMPLEXA) == Tier.OPUS


def test_familias_sao_as_que_o_claude_code_aceita():
    assert TIER_FAMILIA == {Tier.HAIKU: "haiku", Tier.SONNET: "sonnet", Tier.OPUS: "opus", Tier.FABLE: "fable"}
    assert FAMILIA_TIER["opus"] == Tier.OPUS
