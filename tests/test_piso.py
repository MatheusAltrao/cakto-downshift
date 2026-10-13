import json
import os
from pathlib import Path

import pytest

from cakto_downshift.classes import Classe, Tier
from cakto_downshift.piso import (NOME_ARQUIVO, carregar, carregar_da_maquina, carregar_do_projeto, combinar,
                                   encontrar, salvar_maquina, templates, tier_minimo)
from cakto_downshift.vocabulario_risco import Categoria

TEMPLATES = Path(__file__).parent.parent / "src" / "cakto_downshift" / "pisos"


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


def test_templates_viajam_no_pacote():
    assert set(templates()) == {"pagamentos", "front"}


def test_combinar_fica_com_o_maior_em_cada_campo():
    a = carregar(TEMPLATES / "front.json")
    b = carregar(TEMPLATES / "pagamentos.json")
    c = combinar(a, b)
    assert tier_minimo(c, Classe.MECANICA, frozenset({Categoria.DINHEIRO})) == Tier.OPUS
    assert tier_minimo(c, Classe.MECANICA, frozenset({Categoria.ACESSO})) == Tier.SONNET
    assert combinar(a, None) is a and combinar(None, None) is None


def test_piso_da_maquina_global_e_por_projeto(home, tmp_path):
    salvar_maquina(home, {"versao": 1, "minimo_por_risco": {"dado_pessoal": "sonnet"},
                          "por_projeto": {"cakto-backend": {"minimo_por_risco": {"dinheiro": "opus"}}}})
    fora, _ = carregar_da_maquina(home, tmp_path / "outro")
    assert tier_minimo(fora, Classe.MECANICA, frozenset({Categoria.DINHEIRO})) is None
    assert tier_minimo(fora, Classe.MECANICA, frozenset({Categoria.DADO_PESSOAL})) == Tier.SONNET
    # A sessão aberta numa subpasta do repo ainda pega o piso do projeto.
    dentro, _ = carregar_da_maquina(home, tmp_path / "cakto-backend" / "apps" / "x")
    assert tier_minimo(dentro, Classe.MECANICA, frozenset({Categoria.DINHEIRO})) == Tier.OPUS
    assert tier_minimo(dentro, Classe.MECANICA, frozenset({Categoria.DADO_PESSOAL})) == Tier.SONNET
    assert carregar_da_maquina(home, None)[0] is not None


@pytest.mark.parametrize("bruto", [
    {"versao": 1, "por_projeto": []}, {"versao": 1, "por_projeto": {"x": 1}},
    {"versao": 1, "por_projeto": {"x": {"minimo": "turbo"}}}, {"versao": 1, "por_projeto": {"x": {"versao": 1}}},
    {"versao": 2}, {"minimo": "opus"},
])
def test_salvar_maquina_recusa_invalido_e_hook_ignora(home, bruto):
    with pytest.raises(ValueError):
        salvar_maquina(home, bruto)
    home.mkdir(parents=True, exist_ok=True)
    (home / "piso.json").write_text(json.dumps(bruto))
    piso, erro = carregar_da_maquina(home, None)
    assert piso is None and erro


def test_piso_da_maquina_sem_arquivo(home):
    assert carregar_da_maquina(home, Path("/tmp")) == (None, None)
