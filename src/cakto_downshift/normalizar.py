import re
import unicodedata

_CAMEL = re.compile(r"([a-z0-9])([A-Z])")
_ESPACOS = re.compile(r"[ \t]+")


def normalizar(texto: str) -> str:
    """Texto comparável por regex ASCII: sem acento (NFC ou NFD), minúsculo, identificadores abertos.

    A ordem importa: o camelCase é aberto antes do lower(), senão a fronteira some.
    """
    texto = _CAMEL.sub(r"\1 \2", texto).replace("_", " ")
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_marcas = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    return _ESPACOS.sub(" ", sem_marcas.lower()).strip()


def contar_palavras(texto: str) -> int:
    return len(texto.split())
