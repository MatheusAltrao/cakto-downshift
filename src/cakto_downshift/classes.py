from enum import IntEnum


class Classe(IntEnum):
    MECANICA = 0
    SIMPLES = 1
    MEDIA = 2
    COMPLEXA = 3


class Tier(IntEnum):
    HAIKU = 0
    SONNET = 1
    OPUS = 2
    FABLE = 3


# O Claude Code valida `model` contra nomes de família, não ids completos.
TIER_FAMILIA = {Tier.HAIKU: "haiku", Tier.SONNET: "sonnet", Tier.OPUS: "opus", Tier.FABLE: "fable"}
FAMILIA_TIER = {familia: tier for tier, familia in TIER_FAMILIA.items()}


def tier_da_classe(classe: Classe) -> Tier:
    # Mecânica e simples cabem no mesmo tier: o que separa as duas é o sinal, não o modelo.
    if classe <= Classe.SIMPLES:
        return Tier.HAIKU
    if classe == Classe.MEDIA:
        return Tier.SONNET
    return Tier.OPUS
