"""A pasta onde o hook age. O Claude Code só lê settings da raiz de cada projeto, nunca de uma
pasta acima, então "só em trabalho/cakto" não cabe num settings: os hooks são globais e o recorte é aqui."""
import os
from pathlib import Path

ARQUIVO = "escopo"


def carregar(home: Path) -> Path | None:
    try:
        texto = (home / ARQUIVO).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return Path(texto).resolve() if texto else None


def salvar(home: Path, pasta: Path) -> None:
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    (home / ARQUIVO).write_text(str(pasta.resolve()) + "\n", encoding="utf-8")
    os.chmod(home / ARQUIVO, 0o600)


def dentro(raiz: Path | None, escopo: Path | None) -> bool:
    if escopo is None:
        return True
    if raiz is None:
        return False
    try:
        raiz.resolve().relative_to(escopo.resolve())
        return True
    except ValueError:
        return False
