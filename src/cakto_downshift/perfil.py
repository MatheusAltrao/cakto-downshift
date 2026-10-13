"""Quanto o operador quer economizar, por máquina. Mexe só em duas coisas que são gosto, não
segurança: se o tier pequeno entra, e quantos filhos em paralelo. Toda guarda vale em todo perfil."""
import json
import os
import platform
import subprocess
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

ARQUIVO = "perfil.json"
GB_PADRAO = 2.0
MAX_SUBAGENTES_ABSOLUTO = 64


class Economia(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_NOMES = {
    "low": Economia.LOW, "baixa": Economia.LOW, "baixo": Economia.LOW,
    "medium": Economia.MEDIUM, "media": Economia.MEDIUM, "média": Economia.MEDIUM, "medio": Economia.MEDIUM, "médio": Economia.MEDIUM,
    "high": Economia.HIGH, "alta": Economia.HIGH, "alto": Economia.HIGH,
}

# Mais economia, menos filhos: cada um relê contexto e paga os próprios tokens.
TETOS = {Economia.LOW: 6, Economia.MEDIUM: 4, Economia.HIGH: 2}


def interpretar_economia(s: str) -> Economia | None:
    return _NOMES.get((s or "").strip().lower())


@dataclass
class Perfil:
    economia: Economia = Economia.MEDIUM
    max_subagentes: int | None = None
    gb_por_subagente: float = GB_PADRAO
    modelos: tuple[str, ...] = ("haiku", "sonnet", "opus")


def caminho(home: Path) -> Path:
    return home / ARQUIVO


def carregar(home: Path) -> Perfil:
    """Nunca falha: perfil quebrado vira medium. É lido a cada spawn, dentro do hook."""
    padrao = Perfil()
    try:
        bruto = json.loads(caminho(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao
    if not isinstance(bruto, dict):
        return padrao
    p = Perfil()
    if (e := interpretar_economia(str(bruto.get("economia", "")))) is not None:
        p.economia = e
    n = bruto.get("max_subagentes")
    if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= MAX_SUBAGENTES_ABSOLUTO:
        p.max_subagentes = n
    gb = bruto.get("gb_por_subagente")
    if isinstance(gb, (int, float)) and not isinstance(gb, bool) and 0.5 <= gb <= 64:
        p.gb_por_subagente = float(gb)
    modelos = bruto.get("modelos")
    if isinstance(modelos, list) and modelos and all(m in ("haiku", "sonnet", "opus", "fable") for m in modelos):
        p.modelos = tuple(modelos)
    return p


def salvar(home: Path, p: Perfil) -> None:
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    dados = asdict(p)
    dados["economia"] = p.economia.value
    dados["modelos"] = list(p.modelos)
    tmp = caminho(home).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, caminho(home))


@dataclass(frozen=True)
class Orcamento:
    maximo: int
    teto: int
    ram_gb: float | None
    gb_por_subagente: float
    motivo: str  # "fixo" | "memoria" | "teto"


def orcamento(p: Perfil, ram_gb: float | None) -> Orcamento:
    teto = TETOS[p.economia]
    if p.max_subagentes:
        return Orcamento(p.max_subagentes, teto, ram_gb, p.gb_por_subagente, "fixo")
    if ram_gb is not None and ram_gb > 0:
        por_memoria = int(ram_gb // p.gb_por_subagente)
        if por_memoria < teto:
            return Orcamento(max(1, por_memoria), teto, ram_gb, p.gb_por_subagente, "memoria")
    return Orcamento(teto, teto, ram_gb, p.gb_por_subagente, "teto")


def ram_disponivel_gb() -> float | None:
    """Memória disponível, não total: o que já roda na máquina é o que decide quantos filhos cabem.
    O filho em si é uma conversa com a API; o que pesa é a suíte, o navegador ou o dev server que ele roda."""
    try:
        if platform.system() == "Linux":
            for linha in Path("/proc/meminfo").read_text().splitlines():
                if linha.startswith("MemAvailable:"):
                    return int(linha.split()[1]) / (1024 ** 2)
        if platform.system() == "Darwin":
            # Sem número barato de "disponível" no macOS: metade da física é o que o sistema costuma ceder.
            saida = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=1)
            return int(saida.stdout.strip()) / 2 / (1024 ** 3)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def orientacao(o: Orcamento, economia: Economia) -> str:
    motivo = {
        "fixo": "limite fixado pelo operador",
        "memoria": f"{o.ram_gb:.1f} GB de memória disponível, cerca de {o.gb_por_subagente:.1f} GB por subagente",
        "teto": f"teto do perfil {economia.value}",
    }[o.motivo]
    estilo = {
        Economia.HIGH: "Delegue a um subagente só o que não cabe bem no contexto atual, e agrupe tarefas pequenas num subagente em vez de abrir um por item.",
        Economia.LOW: "Pode paralelizar trabalho independente até esse limite.",
        Economia.MEDIUM: "Prefira agrupar tarefas pequenas num subagente só a abrir um por item.",
    }[economia]
    return (f"Orçamento de subagentes desta máquina (cakto-downshift, economia {economia.value}): "
            f"no máximo {o.maximo} subagente(s) em paralelo ({motivo}). {estilo}")
