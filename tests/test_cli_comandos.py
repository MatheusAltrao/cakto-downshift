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
    assert "PreToolUse: 1" in saida and "piso repo" in saida and "inválido" in saida
    assert "da máquina nenhum" in saida


def test_piso_grava_template_global_e_por_projeto(home, tmp_path, capsys, monkeypatch):
    assert main(["piso"]) == 0 and "ausente" in capsys.readouterr().out
    assert main(["piso", "front"]) == 0
    assert main(["piso", "pagamentos", "--projeto", "cakto-backend"]) == 0
    capsys.readouterr()
    assert main(["piso"]) == 0
    saida = capsys.readouterr().out
    assert "global:" in saida and "projeto cakto-backend:" in saida and "dinheiro=opus" in saida
    # O try usa o piso da máquina: dinheiro em opus dentro do cakto-backend, sonnet fora.
    (tmp_path / "cakto-backend").mkdir()
    main(["try", "formate o relatório de chargeback", "--modelo-atual", "opus", "--projeto", str(tmp_path / "cakto-backend")])
    assert "tier:        opus" in capsys.readouterr().out
    main(["try", "formate o relatório de chargeback", "--modelo-atual", "opus", "--projeto", str(tmp_path)])
    assert "tier:        sonnet" in capsys.readouterr().out
    assert main(["piso", "remover", "--projeto", "cakto-backend"]) == 0
    assert main(["piso", "remover", "--projeto", "cakto-backend"]) == 2
    assert main(["piso", "remover"]) == 0
    capsys.readouterr()
    main(["piso"])
    assert "(vazio)" in capsys.readouterr().out


def test_piso_recusa_fonte_ruim(home, tmp_path, capsys):
    assert main(["piso", "turbo"]) == 2
    ruim = tmp_path / "ruim.json"
    ruim.write_text('{"versao": 1, "minimo": "gpt"}')
    assert main(["piso", str(ruim)]) == 2
    assert not (home / "piso.json").exists()
