import json
from pathlib import Path

import pytest

from cakto_downshift.classes import Classe
from cakto_downshift.classificador import MAX_PALAVRAS_TIER_BAIXO, classificar
from cakto_downshift.normalizar import normalizar

GOLDEN = Path(__file__).parent / "golden" / "classes.jsonl"
CASOS = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.mark.parametrize("caso", CASOS, ids=[c["texto"][:40] for c in CASOS])
def test_golden_classes(caso):
    r = classificar(normalizar(caso["texto"]))
    assert r.classe == Classe[caso["classe"].upper()], r.pontos
    assert r.confianca == caso["confianca"], r.pontos


def test_sem_sinal_e_media_sem_confianca():
    r = classificar(normalizar("xyzzy plugh"))
    assert r.classe == Classe.MEDIA and not r.confianca and r.sem_sinal


def test_empate_vai_para_a_classe_mais_alta():
    # "renomeie" (mecânica) e "arquitetura" (complexa) com o mesmo peso: vence complexa.
    r = classificar(normalizar("renomeie a arquitetura"))
    assert r.classe >= Classe.MEDIA


def test_prompt_longo_nao_e_confiante_no_tier_baixo():
    longo = "renomeie a variável e depois " + "leia o módulo com calma " * 12
    r = classificar(normalizar(longo))
    assert len(longo.split()) > MAX_PALAVRAS_TIER_BAIXO
    assert r.classe <= Classe.SIMPLES and not r.confianca


def test_acento_nao_muda_a_classe():
    assert classificar(normalizar("revisão de segurança")).classe == classificar(normalizar("revisao de seguranca")).classe
