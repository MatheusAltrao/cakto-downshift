import re

from cakto_downshift.vocabulario_risco import (
    COMPORTAMENTOS, CONTEXTO, DISTANCIA_CONTEXTO, SUBSTANTIVOS, Categoria,
)

_COMPORTAMENTOS = {c: tuple(re.compile(p) for p in ps) for c, ps in COMPORTAMENTOS.items()}
_SUBSTANTIVOS = {c: tuple(re.compile(p) for p in ps) for c, ps in SUBSTANTIVOS.items()}
_CONTEXTO = {c: tuple(re.compile(p) for p in ps) for c, ps in CONTEXTO.items()}


def _tem_contexto_perto(texto: str, inicio: int, fim: int, contextos) -> bool:
    # Janelas à esquerda e à direita, sem o próprio substantivo: "cobranças" não pode ser o
    # contexto de "cobranças".
    esquerda = texto[max(0, inicio - DISTANCIA_CONTEXTO): inicio]
    direita = texto[fim: fim + DISTANCIA_CONTEXTO]
    return any(r.search(esquerda) or r.search(direita) for r in contextos)


def categorias(texto_normalizado: str) -> frozenset[Categoria]:
    achadas: set[Categoria] = set()
    for cat, regexes in _COMPORTAMENTOS.items():
        if any(r.search(texto_normalizado) for r in regexes):
            achadas.add(cat)
    for cat, regexes in _SUBSTANTIVOS.items():
        if cat in achadas:
            continue
        contextos = _CONTEXTO.get(cat, ())
        for r in regexes:
            for m in r.finditer(texto_normalizado):
                if _tem_contexto_perto(texto_normalizado, m.start(), m.end(), contextos):
                    achadas.add(cat)
                    break
            if cat in achadas:
                break
    return frozenset(achadas)
