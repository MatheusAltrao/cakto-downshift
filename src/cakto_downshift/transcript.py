"""Leitura do transcript JSONL do Claude Code. Só modelo e contagem de tokens saem daqui;
o conteúdo das mensagens nunca é guardado nem devolvido."""
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Transcript de sessão longa passa de 100 MB; o modelo da sessão só precisa da última resposta.
CAUDA_BYTES = 256 * 1024


def _linhas_assistant(caminho: Path, so_cauda: bool):
    try:
        with caminho.open("rb") as f:
            if so_cauda:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - CAUDA_BYTES))
            bruto = f.read()
    except OSError:
        return
    # errors="replace": o corte da cauda pode partir uma sequência UTF-8 no meio.
    for linha in bruto.decode("utf-8", errors="replace").splitlines():
        if '"assistant"' not in linha:
            continue
        try:
            obj = json.loads(linha)
        except ValueError:
            continue
        if obj.get("type") == "assistant" and isinstance(obj.get("message"), dict):
            yield obj["message"]


def modelo_da_sessao(caminho: Path) -> str | None:
    """O modelo que um Task sem `model` herda: o da última resposta do assistente.
    Entradas sintéticas (`<synthetic>`) não são modelo real e são puladas."""
    ultimo = None
    for msg in _linhas_assistant(caminho, so_cauda=True):
        modelo = msg.get("model")
        if isinstance(modelo, str) and modelo and not modelo.startswith("<"):
            ultimo = modelo
    return ultimo


@dataclass(frozen=True)
class Uso:
    entrada: int
    saida: int
    cache_leitura: int
    cache_escrita: int


def uso_do_transcript(caminho: Path) -> Uso:
    e = s = cl = ce = 0
    for msg in _linhas_assistant(caminho, so_cauda=False):
        u = msg.get("usage") or {}
        e += int(u.get("input_tokens") or 0)
        s += int(u.get("output_tokens") or 0)
        cl += int(u.get("cache_read_input_tokens") or 0)
        ce += int(u.get("cache_creation_input_tokens") or 0)
    return Uso(e, s, cl, ce)


def modelo_do_transcript(caminho: Path) -> str | None:
    """Modelo mais frequente nas respostas do filho: um subagente pode trocar de modelo
    no meio, e o preço do que ele gastou segue o que mais rodou."""
    contagem = Counter(
        m["model"] for m in _linhas_assistant(caminho, so_cauda=False)
        if isinstance(m.get("model"), str) and m["model"] and not m["model"].startswith("<")
    )
    return contagem.most_common(1)[0][0] if contagem else None
