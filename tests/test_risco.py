import json
from pathlib import Path

import pytest

from cakto_downshift.normalizar import normalizar
from cakto_downshift.risco import categorias
from cakto_downshift.vocabulario_risco import Categoria

G = Path(__file__).parent / "golden"
ENTRA = [json.loads(l) for l in (G / "risco_entra.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
FORA = [json.loads(l) for l in (G / "risco_fora.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.mark.parametrize("caso", ENTRA, ids=[c["texto"][:40] for c in ENTRA])
def test_risco_entra(caso):
    assert Categoria(caso["risco"]) in categorias(normalizar(caso["texto"]))


@pytest.mark.parametrize("caso", FORA, ids=[c["texto"][:40] for c in FORA])
def test_risco_fora(caso):
    assert categorias(normalizar(caso["texto"])) == frozenset()


def test_identificador_camel_case_e_lido():
    assert Categoria.SEGREDO in categorias(normalizar("troque o apiKey do worker"))
