import json
import os
from pathlib import Path

from cakto_downshift.instalar import aplicar, desinstalar, mesclar, remover
from cakto_downshift.perfil import caminho as perfil_path

EXE = Path("/x y/venv/bin/cakto-downshift")
ALHEIO = {"matcher": "Bash", "hooks": [{"type": "command", "command": "bash deps.sh"}]}
ANTIGO = {"matcher": "Task|Agent", "hooks": [{"type": "command", "command": '"/old/cakto-downshift" hook pre-tool-use'}]}


def test_mesclar_preserva_alheio_troca_antigo_e_e_idempotente():
    s = {"model": "opus", "hooks": {"PreToolUse": [ALHEIO, ANTIGO]}}
    m = mesclar(s, EXE)
    assert m["model"] == "opus"
    cmds = [h["command"] for g in m["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert cmds == ["bash deps.sh", f'"{EXE}" hook pre-tool-use']
    assert set(m["hooks"]) == {"PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStop", "SessionStart"}
    assert mesclar(m, EXE) == m


def test_remover_apaga_eventos_vazios():
    m = mesclar({"hooks": {"PreToolUse": [ALHEIO]}}, EXE)
    r = remover(m)
    assert r["hooks"] == {"PreToolUse": [ALHEIO]}


def test_aplicar_faz_backup_escreve_via_symlink_e_nao_sobrescreve_perfil(home, tmp_path):
    real = tmp_path / "dot" / "settings.json"
    real.parent.mkdir()
    real.write_text(json.dumps({"hooks": {"PreToolUse": [ALHEIO]}}))
    os.chmod(real, 0o644)
    link = tmp_path / "settings.json"
    os.symlink(real, link)
    perfil_path(home).parent.mkdir(parents=True)
    perfil_path(home).write_text('{"economia": "high"}')
    feitos = aplicar(link, home, tmp_path / "escopo", EXE)
    assert link.is_symlink() and "SessionStart" in json.loads(real.read_text())["hooks"]
    assert oct(real.stat().st_mode & 0o777) == "0o644"
    assert any(p.name.startswith("settings.json.bak-") for p in real.parent.iterdir())
    assert json.loads(perfil_path(home).read_text())["economia"] == "high"
    assert (home / "escopo").read_text().strip() == str((tmp_path / "escopo").resolve())
    assert any("backup" in f for f in feitos)


def test_aplicar_cria_settings_e_perfil_quando_nao_existem(home, tmp_path):
    s = tmp_path / ".claude" / "settings.json"
    aplicar(s, home, None, EXE)
    assert "PreToolUse" in json.loads(s.read_text())["hooks"]
    assert json.loads(perfil_path(home).read_text())["economia"] == "medium"
    desinstalar(s)
    assert json.loads(s.read_text()).get("hooks", {}) == {}


def test_dois_aplicar_no_mesmo_segundo_mantem_o_backup_original(home, tmp_path):
    s = tmp_path / "settings.json"
    original = json.dumps({"model": "opus"})
    s.write_text(original)
    aplicar(s, home, None, EXE)
    aplicar(s, home, None, EXE)
    baks = sorted(tmp_path.glob("settings.json.bak-*"))
    assert len(baks) == 2
    assert any(b.read_text() == original for b in baks)


def test_grupo_sem_hooks_sobrevive(home):
    s = {"hooks": {"Stop": [{"matcher": "x"}, {"matcher": "y", "hooks": []}]}}
    assert mesclar(s, EXE)["hooks"]["Stop"] == s["hooks"]["Stop"]
    assert remover(s) == s


def test_aplicar_via_symlink_mantem_link_e_modo_600(home, tmp_path):
    real = tmp_path / "dot" / "settings.json"
    real.parent.mkdir()
    real.write_text("{}")
    os.chmod(real, 0o600)
    link = tmp_path / "settings.json"
    os.symlink(real, link)
    aplicar(link, home, None, EXE)
    assert link.is_symlink()
    assert "SessionStart" in json.loads(real.read_text())["hooks"]
    assert oct(real.stat().st_mode & 0o777) == "0o600"
    assert not [p for p in real.parent.iterdir() if p.name.startswith(".settings.json.")]


def test_json_invalido_da_rc1_sem_tocar_em_nada(home, tmp_path, monkeypatch, capsys):
    from cakto_downshift.cli import main
    s = tmp_path / "settings.json"
    s.write_bytes(b'{"model":"opus",}')
    monkeypatch.setenv("CAKTO_DOWNSHIFT_SETTINGS", str(s))
    assert main(["instalar", "--aplicar"]) == 1
    assert "não é um JSON válido" in capsys.readouterr().err
    assert s.read_bytes() == b'{"model":"opus",}'
    assert not list(tmp_path.glob("settings.json.bak-*"))
    assert not perfil_path(home).exists()


def test_hooks_malformado_no_settings_nao_derruba_nem_apaga():
    import pytest
    s = {"hooks": {"Stop": [{"hooks": ["x", {"command": 5}]}], "Notification": "abc"}}
    m = mesclar(s, EXE)
    assert m["hooks"]["Stop"] == [{"hooks": ["x", {"command": 5}]}] and m["hooks"]["Notification"] == "abc"
    assert remover(m)["hooks"] == s["hooks"]
    with pytest.raises(ValueError, match="não é uma lista"):
        mesclar({"hooks": {"PreToolUse": "abc"}}, EXE)
