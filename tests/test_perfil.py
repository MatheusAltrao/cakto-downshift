import json
import os

import pytest

from cakto_downshift.perfil import (
    Economia, Perfil, caminho, carregar, interpretar_economia, orcamento, orientacao, salvar,
)


@pytest.mark.parametrize("s,esperado", [
    ("low", Economia.LOW), ("Baixa", Economia.LOW), ("MEDIUM", Economia.MEDIUM), ("média", Economia.MEDIUM),
    ("alta", Economia.HIGH), ("high ", Economia.HIGH), ("turbo", None), ("", None),
])
def test_interpretar_economia(s, esperado):
    assert interpretar_economia(s) == esperado


def test_sem_arquivo_e_medium(home):
    assert carregar(home) == Perfil()


def test_salvar_e_carregar_com_modo_0600(home):
    salvar(home, Perfil(economia=Economia.HIGH, max_subagentes=3))
    assert carregar(home) == Perfil(economia=Economia.HIGH, max_subagentes=3)
    assert oct(caminho(home).stat().st_mode & 0o777) == "0o600"
    assert oct(home.stat().st_mode & 0o777) == "0o700"


def test_arquivo_invalido_cai_no_padrao(home):
    home.mkdir(parents=True)
    caminho(home).write_text('{"economia": "turbo", "max_subagentes": 999, "gb_por_subagente": -1}')
    assert carregar(home) == Perfil()
    caminho(home).write_text("{nao e json")
    assert carregar(home) == Perfil()


@pytest.mark.parametrize("perfil,ram,maximo,motivo", [
    (Perfil(Economia.MEDIUM), 30.0, 4, "teto"),
    (Perfil(Economia.LOW), 30.0, 6, "teto"),
    (Perfil(Economia.HIGH), 30.0, 2, "teto"),
    (Perfil(Economia.LOW), 7.0, 3, "memoria"),
    (Perfil(Economia.MEDIUM), 0.5, 1, "memoria"),
    (Perfil(Economia.MEDIUM), None, 4, "teto"),
    (Perfil(Economia.HIGH, max_subagentes=5), 1.0, 5, "fixo"),
    (Perfil(Economia.LOW, gb_por_subagente=4.0), 10.0, 2, "memoria"),
])
def test_orcamento(perfil, ram, maximo, motivo):
    o = orcamento(perfil, ram)
    assert (o.maximo, o.motivo) == (maximo, motivo)


def test_orientacao_cita_o_limite():
    texto = orientacao(orcamento(Perfil(Economia.HIGH), 30.0), Economia.HIGH)
    assert "no máximo 2 subagente" in texto and "high" in texto
