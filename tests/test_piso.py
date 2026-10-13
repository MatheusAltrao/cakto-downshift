import json
import os
from pathlib import Path

import pytest

from cakto_downshift.classes import Classe, Tier
from cakto_downshift.piso import NOME_ARQUIVO, carregar, carregar_do_projeto, encontrar, tier_minimo
from cakto_downshift.vocabulario_risco import Categoria

TEMPLATES = Path(__file__).parent.parent / "docs" / "pisos"


@pytest.mark.parametrize("nome", ["pagamentos.json", "front.json"])
def test_templates_carregam(nome):
    p = carregar(TEMPLATES / nome)
    assert tier_minimo(p, Classe.MECANICA, frozenset({Categoria.SEGREDO})) == Tier.OPUS


def test_pagamentos_poe_dinheiro_no_opus_e_front_no_sonnet():
    pag, front = carregar(TEMPLATES / "pagamentos.json"), carregar(TEMPLATES / "front.json")
    assert tier_minimo(pag, Classe.MECANICA, frozenset({Categoria.DINHEIRO})) == Tier.OPUS
    assert tier_minimo(front, Classe.MECANICA, frozenset({Categoria.DINHEIRO})) == Tier.SONNET


def test_encontrar_sobe_ate_oito_niveis_e_para(tmp_path):
    raiz = tmp_path / "repo"
    fundo = raiz.joinpath(*["d"] * 7)
    fundo.mkdir(parents=True)
    (raiz / NOME_ARQUIVO).write_text("{}")
    assert encontrar(fundo) == raiz / NOME_ARQUIVO
    no_limite = raiz.joinpath(*["d"] * 8)
    no_limite.mkdir(parents=True)
    assert encontrar(no_limite) == raiz / NOME_ARQUIVO
    mais_fundo = raiz.joinpath(*["d"] * 9)
    mais_fundo.mkdir(parents=True)
    assert encontrar(mais_fundo) is None


def test_symlink_e_ignorado(tmp_path):
    alvo = tmp_path / "alvo.json"
    alvo.write_text('{"versao": 1, "minimo": "opus"}')
    os.symlink(alvo, tmp_path / NOME_ARQUIVO)
    assert encontrar(tmp_path) is None


@pytest.mark.parametrize("conteudo", [
    '{"versao": 2}', '{"versao": 1, "minimo": "turbo"}', '{"versao": 1, "minimo_por_classe": {"x": "opus"}}',
    '{"versao": 1, "minimo_por_risco": {"dinheiro": "gpt"}}', '{"versao": 1, "campo_desconhecido": 1}', "[]", "{",
    '{"versao": 1, "minimo_por_classe": [1]}', '{"versao": 1, "minimo_por_risco": "x"}',
    '{"versao": 1, "minimo_por_classe": []}', "[" * 60000,
])
def test_invalido_lanca_valueerror_e_projeto_fail_open(tmp_path, conteudo):
    arq = tmp_path / NOME_ARQUIVO
    arq.write_text(conteudo)
    with pytest.raises(ValueError):
        carregar(arq)
    piso, erro = carregar_do_projeto(tmp_path)
    assert piso is None and erro and str(arq) in erro


def test_so_sobe_e_o_maior_vence(tmp_path):
    (tmp_path / NOME_ARQUIVO).write_text(json.dumps({
        "versao": 1, "minimo": "haiku", "minimo_por_classe": {"media": "sonnet"}, "minimo_por_risco": {"acesso": "opus"},
    }))
    p, _ = carregar_do_projeto(tmp_path)
    assert tier_minimo(p, Classe.MECANICA, frozenset()) == Tier.HAIKU
    assert tier_minimo(p, Classe.MEDIA, frozenset({Categoria.ACESSO})) == Tier.OPUS


def test_sem_arquivo(tmp_path):
    assert carregar_do_projeto(tmp_path) == (None, None)
