import unicodedata

from cakto_downshift.normalizar import contar_palavras, normalizar


def test_remove_acento_nfc_e_nfd():
    assert normalizar("revisão da segurança") == "revisao da seguranca"
    assert normalizar(unicodedata.normalize("NFD", "revisão da segurança")) == "revisao da seguranca"


def test_minusculas_e_identificadores_abertos():
    assert normalizar("renomeie saldoTotal e taxa_de_servico") == "renomeie saldo total e taxa de servico"


def test_preserva_pontuacao_e_espacos_simples():
    assert normalizar("rm -rf /tmp; drop table users") == "rm -rf /tmp; drop table users"


def test_contar_palavras():
    assert contar_palavras("  renomeie a   variavel ") == 3
    assert contar_palavras("") == 0
