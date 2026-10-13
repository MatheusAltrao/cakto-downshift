"""Eventos JSONL. Regra única: nada do prompt, nada do caminho completo. Quem grava é um hook com
orçamento de milissegundos, então gravar nunca lança e nunca bloqueia."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ARQUIVO = "eventos.jsonl"


def hash_sessao(session_id: str | None) -> str | None:
    if not session_id:
        return None
    return hashlib.sha256(session_id.encode()).hexdigest()[:16]


def nome_projeto(cwd: str | None) -> str | None:
    return Path(cwd).name if cwd else None


def gravar(home: Path, evento: dict) -> None:
    try:
        home.mkdir(parents=True, exist_ok=True)
        os.chmod(home, 0o700)
        evento.setdefault("ts", datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
        caminho = home / ARQUIVO
        with caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evento, ensure_ascii=False, separators=(",", ":")) + "\n")
        os.chmod(caminho, 0o600)
    except (OSError, TypeError, ValueError):
        pass


def ler(home: Path, desde: datetime | None = None) -> list[dict]:
    try:
        linhas = (home / ARQUIVO).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    saida = []
    for linha in linhas:
        try:
            ev = json.loads(linha)
        except ValueError:
            continue
        if desde is not None:
            try:
                if datetime.fromisoformat(ev["ts"]) < desde:
                    continue
            except (KeyError, ValueError, TypeError):
                continue
        saida.append(ev)
    return saida
