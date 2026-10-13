"""Da tarefa à decisão. Puro: nada aqui lê disco ou ambiente.

Ordem: classe → risco (piso) → piso do repo → piso do perfil → guardas. Tudo que sobe tier vem
antes das guardas, e as guardas valem em qualquer perfil.
"""
from dataclasses import dataclass

from cakto_downshift.classes import FAMILIA_TIER, TIER_FAMILIA, Classe, Tier, tier_da_classe
from cakto_downshift.classificador import classificar
from cakto_downshift.normalizar import normalizar
from cakto_downshift.perfil import Economia, Perfil
from cakto_downshift.piso import Piso, tier_minimo
from cakto_downshift.risco import categorias
from cakto_downshift.vocabulario_risco import Categoria

AGENTES_QUE_HERDAM = frozenset({"", "general-purpose"})


@dataclass(frozen=True)
class Entrada:
    texto: str
    familia_atual: str | None
    agente: str | None
    perfil: Perfil
    piso: Piso | None = None
    rotear_nomeados: bool = False


@dataclass(frozen=True)
class Decisao:
    classe: Classe
    confianca: bool
    riscos: frozenset[Categoria]
    tier: Tier
    familia_atual: str | None
    familia_escrita: str | None
    motivos: tuple[str, ...]
    piso_perfil: bool
    piso_repo: bool
    sem_sinal: bool


def decidir(e: Entrada) -> Decisao:
    texto = normalizar(e.texto)
    cls = classificar(texto)
    riscos = categorias(texto)
    motivos: list[str] = []
    tier = tier_da_classe(cls.classe)
    confianca = cls.confianca
    motivos.append("SEM_SINAL" if cls.sem_sinal else ("CLASSE_CONFIANTE" if confianca else "CLASSE_SEM_CONFIANCA"))

    if riscos:
        motivos.extend(f"RISCO_{r.value.upper()}" for r in sorted(riscos, key=lambda r: r.value))
        confianca = False
        if tier < Tier.SONNET:
            tier = Tier.SONNET
            motivos.append("PISO_RISCO")

    piso_repo = False
    if e.piso is not None:
        minimo = tier_minimo(e.piso, cls.classe, riscos)
        if minimo is not None and minimo > tier:
            tier, piso_repo = minimo, True
            motivos.append("PISO_REPO")

    piso_perfil = False
    if e.perfil.economia == Economia.LOW and tier == Tier.HAIKU:
        tier, piso_perfil = Tier.SONNET, True
        motivos.append("PISO_PERFIL")

    escrita = _guardas(e, cls.classe, confianca, riscos, tier, piso_repo, motivos)
    return Decisao(cls.classe, confianca, riscos, tier, e.familia_atual, escrita, tuple(motivos), piso_perfil, piso_repo, cls.sem_sinal)


def _guardas(e: Entrada, classe: Classe, confianca: bool, riscos, tier: Tier, piso_repo: bool, motivos: list[str]) -> str | None:
    """Devolve a família a escrever, ou None. Cada None vem com o motivo."""
    if (e.agente or "") not in AGENTES_QUE_HERDAM and not e.rotear_nomeados:
        motivos.append("GUARDA_AGENTE_NOMEADO")
        return None
    atual = FAMILIA_TIER.get(e.familia_atual or "")
    if atual is None:
        motivos.append("GUARDA_MODELO_DESCONHECIDO")
        return None
    if tier == atual:
        return None
    if tier < atual:
        if classe == Classe.COMPLEXA:
            motivos.append("GUARDA_COMPLEXA")
            return None
        if riscos:
            motivos.append("GUARDA_RISCO")
            return None
        if not confianca:
            # O único degrau sem confiança: opus → sonnet no perfil high, sem risco e sem complexa.
            if e.perfil.economia == Economia.HIGH and atual == Tier.OPUS:
                tier = Tier.SONNET
                motivos.append("PERFIL_HIGH")
            else:
                motivos.append("GUARDA_SEM_CONFIANCA")
                return None
    elif not (confianca or piso_repo or riscos):
        motivos.append("GUARDA_SEM_CONFIANCA")
        return None
    familia = TIER_FAMILIA[tier]
    if familia not in e.perfil.modelos:
        motivos.append("GUARDA_FORA_DA_LISTA")
        return None
    return familia
