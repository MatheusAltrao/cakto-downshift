"""Piso de tier: um mínimo que só sobe. Mora na máquina de quem usa (`~/.cakto-downshift/piso.json`),
com um bloco global e, opcionalmente, um por nome de projeto; um `cakto-downshift.json` na raiz do
repo também vale, como extra. Inválido é ignorado (fail-open), e o doctor avisa onde, porque um piso
que some em silêncio é o pior dos dois erros."""
import json
import os
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from cakto_downshift.classes import FAMILIA_TIER, Classe, Tier
from cakto_downshift.vocabulario_risco import Categoria

NOME_ARQUIVO = "cakto-downshift.json"
ARQUIVO_MAQUINA = "piso.json"
MAX_NIVEIS = 8
MAX_BYTES = 64 * 1024
VERSAO = 1
_CAMPOS = {"versao", "minimo", "minimo_por_classe", "minimo_por_risco"}
_CAMPOS_MAQUINA = _CAMPOS | {"por_projeto"}


@dataclass(frozen=True)
class Piso:
    minimo: Tier | None = None
    por_classe: dict[Classe, Tier] = field(default_factory=dict)
    por_risco: dict[Categoria, Tier] = field(default_factory=dict)


def caminho_maquina(home: Path) -> Path:
    return home / ARQUIVO_MAQUINA


def templates() -> dict[str, Path]:
    """Os pisos prontos que viajam no pacote, por nome (`pagamentos`, `front`)."""
    pasta = resources.files("cakto_downshift") / "pisos"
    return {Path(str(a)).stem: Path(str(a)) for a in pasta.iterdir() if str(a).endswith(".json")}


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


def _objeto_ou_ausente(bruto: dict, campo: str) -> bool:
    valor = bruto.get(campo)
    return valor is None or isinstance(valor, dict)


def _ler_json(caminho: Path) -> dict:
    if caminho.stat().st_size > MAX_BYTES:
        raise ValueError(f"{caminho}: maior que {MAX_BYTES} bytes")
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (ValueError, RecursionError) as e:
        # Aninhamento profundo estoura a pilha do parser: é JSON inválido para este arquivo, não um erro do hook.
        raise ValueError(f"{caminho}: JSON inválido ({e})") from e
    if not isinstance(bruto, dict):
        raise ValueError(f"{caminho}: o conteúdo precisa ser um objeto")
    return bruto


def interpretar(bruto: dict, onde: str, com_versao: bool = True, campos: set[str] = _CAMPOS) -> Piso:
    if com_versao and bruto.get("versao") != VERSAO:
        raise ValueError(f"{onde}: versao precisa ser {VERSAO}")
    if desconhecidos := set(bruto) - campos:
        raise ValueError(f"{onde}: campos desconhecidos {sorted(desconhecidos)}")
    minimo = _tier(bruto["minimo"], f"{onde}: minimo") if "minimo" in bruto else None
    por_classe, por_risco = {}, {}
    if not _objeto_ou_ausente(bruto, "minimo_por_classe"):
        raise ValueError(f"{onde}: minimo_por_classe precisa ser um objeto")
    if not _objeto_ou_ausente(bruto, "minimo_por_risco"):
        raise ValueError(f"{onde}: minimo_por_risco precisa ser um objeto")
    for nome, valor in (bruto.get("minimo_por_classe") or {}).items():
        try:
            classe = Classe[nome.upper()]
        except KeyError:
            raise ValueError(f"{onde}: classe desconhecida {nome!r}") from None
        por_classe[classe] = _tier(valor, f"{onde}: minimo_por_classe.{nome}")
    for nome, valor in (bruto.get("minimo_por_risco") or {}).items():
        try:
            cat = Categoria(nome)
        except ValueError:
            raise ValueError(f"{onde}: categoria de risco desconhecida {nome!r}") from None
        por_risco[cat] = _tier(valor, f"{onde}: minimo_por_risco.{nome}")
    return Piso(minimo, por_classe, por_risco)


def carregar(caminho: Path) -> Piso:
    return interpretar(_ler_json(caminho), str(caminho))


def carregar_do_projeto(inicio: Path) -> tuple[Piso | None, str | None]:
    caminho = encontrar(inicio)
    if caminho is None:
        return None, None
    try:
        return carregar(caminho), None
    except (OSError, ValueError) as e:
        return None, str(e)


def interpretar_maquina(bruto: dict, onde: str) -> tuple[Piso, dict[str, Piso]]:
    """O arquivo da máquina: o bloco global mais `por_projeto`, um piso por nome de pasta."""
    geral = interpretar(bruto, onde, campos=_CAMPOS_MAQUINA)
    projetos: dict[str, Piso] = {}
    por_projeto = bruto.get("por_projeto")
    if por_projeto is not None and not isinstance(por_projeto, dict):
        raise ValueError(f"{onde}: por_projeto precisa ser um objeto")
    for nome, sub in (por_projeto or {}).items():
        if not isinstance(sub, dict):
            raise ValueError(f"{onde}: por_projeto.{nome} precisa ser um objeto")
        # A versão é do arquivo, não do bloco: aceitá-la aqui esconderia um template colado inteiro.
        projetos[nome] = interpretar(sub, f"{onde}: por_projeto.{nome}", com_versao=False, campos=_CAMPOS - {"versao"})
    return geral, projetos


def nomes_do_caminho(inicio: Path | None) -> list[str]:
    """O nome da pasta e dos pais, até 8 níveis: a sessão pode abrir numa subpasta do repo."""
    if inicio is None:
        return []
    nomes, atual = [], inicio
    for _ in range(MAX_NIVEIS + 1):
        if atual.name:
            nomes.append(atual.name)
        if atual.parent == atual:
            break
        atual = atual.parent
    return nomes


def carregar_da_maquina(home: Path, inicio: Path | None) -> tuple[Piso | None, str | None]:
    caminho = caminho_maquina(home)
    if not caminho.is_file():
        return None, None
    try:
        geral, projetos = interpretar_maquina(_ler_json(caminho), str(caminho))
    except (OSError, ValueError) as e:
        return None, str(e)
    # O projeto mais próximo da pasta da sessão vence; o global vale sempre.
    do_projeto = next((projetos[n] for n in nomes_do_caminho(inicio) if n in projetos), None)
    return combinar(geral, do_projeto), None


def combinar(a: Piso | None, b: Piso | None) -> Piso | None:
    """Dois pisos viram um: em cada campo fica o maior, porque piso só sobe."""
    if a is None or b is None:
        return a or b

    def maior(x: Tier | None, y: Tier | None) -> Tier | None:
        return max(t for t in (x, y) if t is not None) if (x or y) else None

    return Piso(
        maior(a.minimo, b.minimo),
        {k: maior(a.por_classe.get(k), b.por_classe.get(k)) for k in set(a.por_classe) | set(b.por_classe)},
        {k: maior(a.por_risco.get(k), b.por_risco.get(k)) for k in set(a.por_risco) | set(b.por_risco)},
    )


def salvar_maquina(home: Path, bruto: dict) -> None:
    """Grava o arquivo da máquina depois de validar: piso inválido não chega ao disco."""
    interpretar_maquina(bruto, ARQUIVO_MAQUINA)
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    tmp = caminho_maquina(home).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(bruto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, caminho_maquina(home))


def tier_minimo(p: Piso, classe: Classe, riscos: frozenset[Categoria]) -> Tier | None:
    candidatos = [p.minimo, p.por_classe.get(classe), *(p.por_risco.get(r) for r in riscos)]
    validos = [t for t in candidatos if t is not None]
    return max(validos) if validos else None
