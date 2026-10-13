import json

from cakto_downshift.cli import main
from cakto_downshift.perfil import Economia, carregar


def test_try_mostra_decisao(home, capsys):
    assert main(["try", "renomeie a variável userId", "--modelo-atual", "opus"]) == 0
    saida = capsys.readouterr().out
    assert "mecanica" in saida and "haiku" in saida and "CLASSE_CONFIANTE" in saida


def test_try_com_risco_e_agente(home, capsys):
    main(["try", "formate o relatório de chargeback", "--modelo-atual", "opus", "--agente", "backend"])
    saida = capsys.readouterr().out
    assert "dinheiro" in saida and "GUARDA_AGENTE_NOMEADO" in saida


def test_economia_mostra_e_troca(home, capsys):
    assert main(["economia"]) == 0 and "medium" in capsys.readouterr().out
    assert main(["economia", "alta"]) == 0 and carregar(home).economia == Economia.HIGH
    assert "próximo subagente" in capsys.readouterr().out
    assert main(["economia", "subagentes", "3"]) == 0 and carregar(home).max_subagentes == 3
    assert main(["economia", "subagentes", "auto"]) == 0 and carregar(home).max_subagentes is None
    assert main(["economia", "gb", "3"]) == 0 and carregar(home).gb_por_subagente == 3.0


def test_economia_rejeita_valores(home, capsys):
    for args in (["economia", "turbo"], ["economia", "subagentes", "2.7"], ["economia", "subagentes", "0"], ["economia", "gb", "0.1"]):
        assert main(args) == 2, args


def test_doctor(home, tmp_path, monkeypatch, capsys):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Task|Agent", "hooks": [{"type": "command", "command": '"/x/cakto-downshift" hook pre-tool-use'}]}]}}))
    monkeypatch.setenv("CAKTO_DOWNSHIFT_SETTINGS", str(settings))
    (tmp_path / "cakto-downshift.json").write_text("{versao: 1}")
    monkeypatch.chdir(tmp_path)
    assert main(["doctor"]) == 0
    saida = capsys.readouterr().out
    assert "PreToolUse: 1" in saida and "piso" in saida and "inválido" in saida
