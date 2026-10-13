"""Piso por repositório: um arquivo na raiz que só sobe tier. Inválido é ignorado (fail-open),
e o doctor avisa onde, porque um piso que some em silêncio é o pior dos dois erros."""
import json
from dataclasses import dataclass, field
from pathlib import Path

from cakto_downshift.classes import FAMILIA_TIER, Classe, Tier
from cakto_downshift.vocabulario_risco import Categoria

NOME_ARQUIVO = "cakto-downshift.json"
MAX_NIVEIS = 8
MAX_BYTES = 64 * 1024
VERSAO = 1
_CAMPOS = {"versao", "minimo", "minimo_por_classe", "minimo_por_risco"}


@dataclass(frozen=True)
class Piso:
    minimo: Tier | None = None
    por_classe: dict[Classe, Tier] = field(default_factory=dict)
    por_risco: dict[Categoria, Tier] = field(default_factory=dict)


def encontrar(inicio: Path) -> Path | None:
    atual = inicio
    for _ in range(MAX_NIVEIS + 1):
        candidato = atual / NOME_ARQUIVO
        # Symlink fica de fora: o arquivo precisa estar no repo, não apontando para fora dele.
        if candidato.is_file() and not candidato.is_symlink():
            return candidato
        if atual.parent == atual:
            return None
        atual = atual.parent
    return None


def _tier(valor, onde: str) -> Tier:
    if not isinstance(valor, str) or valor not in FAMILIA_TIER:
        raise ValueError(f"{onde}: tier inválido {valor!r} (use haiku, sonnet, opus ou fable)")
    return FAMILIA_TIER[valor]


def _objeto_ou_ausente(bruto: dict, campo: str, caminho: Path) -> bool:
    valor = bruto.get(campo)
    return valor is None or isinstance(valor, dict)


def carregar(caminho: Path) -> Piso:
    if caminho.stat().st_size > MAX_BYTES:
        raise ValueError(f"{caminho}: maior que {MAX_BYTES} bytes")
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (ValueError, RecursionError) as e:
        # Aninhamento profundo estoura a pilha do parser: é JSON inválido para este arquivo, não um erro do hook.
        raise ValueError(f"{caminho}: JSON inválido ({e})") from e
    if not isinstance(bruto, dict):
        raise ValueError(f"{caminho}: o conteúdo precisa ser um objeto")
    if bruto.get("versao") != VERSAO:
        raise ValueError(f"{caminho}: versao precisa ser {VERSAO}")
    if desconhecidos := set(bruto) - _CAMPOS:
        raise ValueError(f"{caminho}: campos desconhecidos {sorted(desconhecidos)}")
    minimo = _tier(bruto["minimo"], f"{caminho}: minimo") if "minimo" in bruto else None
    por_classe, por_risco = {}, {}
    if not _objeto_ou_ausente(bruto, "minimo_por_classe", caminho):
        raise ValueError(f"{caminho}: minimo_por_classe precisa ser um objeto")
    if not _objeto_ou_ausente(bruto, "minimo_por_risco", caminho):
        raise ValueError(f"{caminho}: minimo_por_risco precisa ser um objeto")
    for nome, valor in (bruto.get("minimo_por_classe") or {}).items():
        try:
            classe = Classe[nome.upper()]
        except KeyError:
            raise ValueError(f"{caminho}: classe desconhecida {nome!r}") from None
        por_classe[classe] = _tier(valor, f"{caminho}: minimo_por_classe.{nome}")
    for nome, valor in (bruto.get("minimo_por_risco") or {}).items():
        try:
            cat = Categoria(nome)
        except ValueError:
            raise ValueError(f"{caminho}: categoria de risco desconhecida {nome!r}") from None
        por_risco[cat] = _tier(valor, f"{caminho}: minimo_por_risco.{nome}")
    return Piso(minimo, por_classe, por_risco)


def carregar_do_projeto(inicio: Path) -> tuple[Piso | None, str | None]:
    caminho = encontrar(inicio)
    if caminho is None:
        return None, None
    try:
        return carregar(caminho), None
    except (OSError, ValueError) as e:
        return None, str(e)


def tier_minimo(p: Piso, classe: Classe, riscos: frozenset[Categoria]) -> Tier | None:
    candidatos = [p.minimo, p.por_classe.get(classe), *(p.por_risco.get(r) for r in riscos)]
    validos = [t for t in candidatos if t is not None]
    return max(validos) if validos else None
