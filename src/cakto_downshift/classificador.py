import re
from dataclasses import dataclass

from cakto_downshift.classes import Classe
from cakto_downshift.normalizar import contar_palavras
from cakto_downshift.sinais import SINAIS

MARGEM_CONFIANCA = 2
# Um brief de 60 palavras com um "renomeie" descreve trabalho que a palavra não cobre.
MAX_PALAVRAS_TIER_BAIXO = 40

_COMPILADOS = tuple((re.compile(s.padrao), s.peso, s.classe) for s in SINAIS)


@dataclass(frozen=True)
class Classificacao:
    classe: Classe
    pontos: dict[Classe, int]
    confianca: bool
    sem_sinal: bool


def classificar(texto_normalizado: str) -> Classificacao:
    pontos = {c: 0 for c in Classe}
    for regex, peso, classe in _COMPILADOS:
        if regex.search(texto_normalizado):
            pontos[classe] += peso
    if not any(pontos.values()):
        return Classificacao(Classe.MEDIA, pontos, confianca=False, sem_sinal=True)
    # Empate sobe: na dúvida entre duas classes, a mais alta custa menos que subestimar.
    vencedora = max(Classe, key=lambda c: (pontos[c], c))
    segunda = max(pontos[c] for c in Classe if c != vencedora)
    confianca = pontos[vencedora] - segunda >= MARGEM_CONFIANCA
    if vencedora <= Classe.SIMPLES and contar_palavras(texto_normalizado) > MAX_PALAVRAS_TIER_BAIXO:
        confianca = False
    return Classificacao(vencedora, pontos, confianca, sem_sinal=False)
