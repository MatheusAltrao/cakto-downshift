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
    # split("\n") e não splitlines(): splitlines também quebra em U+2028 e \x0b, que podem
    # aparecer crus dentro de string JSON e partiriam uma linha válida em pedaços inválidos.
    for linha in bruto.decode("utf-8", errors="replace").split("\n"):
        if '"assistant"' not in linha:
            continue
        try:
            obj = json.loads(linha)
        except ValueError:
            continue
        # Linha JSON que não é objeto (lista, string) passa pelo filtro acima e não tem .get.
        if not isinstance(obj, dict):
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


def _inteiro(valor) -> int:
    # Contagem malformada (string, null, lista) conta como zero: uma linha ruim não pode
    # abortar a soma do transcript inteiro.
    if isinstance(valor, bool):
        return 0
    try:
        return int(valor)
    except (TypeError, ValueError, OverflowError):
        # OverflowError: JSON aceita Infinity, e int(float('inf')) levanta isso.
        return 0


def uso_do_transcript(caminho: Path) -> Uso:
    e = s = cl = ce = 0
    for msg in _linhas_assistant(caminho, so_cauda=False):
        u = msg.get("usage")
        if not isinstance(u, dict):
            continue
        e += _inteiro(u.get("input_tokens"))
        s += _inteiro(u.get("output_tokens"))
        cl += _inteiro(u.get("cache_read_input_tokens"))
        ce += _inteiro(u.get("cache_creation_input_tokens"))
    return Uso(e, s, cl, ce)


def modelo_do_transcript(caminho: Path) -> str | None:
    """Modelo mais frequente nas respostas do filho: um subagente pode trocar de modelo
    no meio, e o preço do que ele gastou segue o que mais rodou."""
    contagem = Counter(
        m["model"] for m in _linhas_assistant(caminho, so_cauda=False)
        if isinstance(m.get("model"), str) and m["model"] and not m["model"].startswith("<")
    )
    return contagem.most_common(1)[0][0] if contagem else None
