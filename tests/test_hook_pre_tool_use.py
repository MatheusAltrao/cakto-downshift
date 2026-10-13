import json

import pytest

from cakto_downshift.escopo import salvar as salvar_escopo
from cakto_downshift.hooks.claude_code import pre_tool_use
from cakto_downshift.perfil import Economia, Perfil, salvar as salvar_perfil
from cakto_downshift.telemetria import ler


def payload(prompt, modelo="claude-opus-5-5", agente="general-purpose", cwd="/tmp/proj", **extra):
    ti = {"prompt": prompt, "subagent_type": agente, "description": "x"}
    if modelo:
        ti["model"] = modelo
    return {"session_id": "s1", "cwd": cwd, "tool_name": "Task", "tool_use_id": "t1", "tool_input": ti, **extra}


def test_rename_em_opus_escreve_haiku_e_preserva_campos(home):
    r = pre_tool_use(payload("renomeie a variável userId para customerId"), home, {})
    hso = r["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse" and hso["permissionDecision"] == "allow"
    assert hso["updatedInput"]["model"] == "haiku" and hso["updatedInput"]["prompt"].startswith("renomeie")
    ev = ler(home)[-1]
    assert ev["tipo"] == "decisao" and ev["familia_escrita"] == "haiku" and ev["tool_use_id"] == "t1"
    assert "prompt" not in json.dumps(ev) and "userId" not in json.dumps(ev) and ev["projeto"] == "proj"


def test_sem_mudanca_responde_vazio_sem_decisao_de_permissao(home):
    assert pre_tool_use(payload("dê uma olhada no módulo e me diga o que acha"), home, {}) == {}
    assert pre_tool_use(payload("renomeie x", modelo="haiku"), home, {}) == {}


def test_modelo_herdado_do_transcript(home, tmp_path):
    t = tmp_path / "s.jsonl"
    t.write_text(json.dumps({"type": "assistant", "message": {"model": "claude-opus-5-5"}}) + "\n")
    r = pre_tool_use(payload("renomeie a variável userId", modelo=None, transcript_path=str(t)), home, {})
    assert r["hookSpecificOutput"]["updatedInput"]["model"] == "haiku"


def test_fora_do_escopo_nao_decide_nem_grava(home, tmp_path):
    salvar_escopo(home, tmp_path / "cakto")
    assert pre_tool_use(payload("renomeie x", cwd=str(tmp_path / "outro")), home, {}) == {}
    assert ler(home) == []
    (tmp_path / "cakto" / "repo").mkdir(parents=True)
    r = pre_tool_use(payload("renomeie a variável userId", cwd=str(tmp_path / "cakto" / "repo")), home, {})
    assert "updatedInput" in r["hookSpecificOutput"]


def test_claude_project_dir_vence_o_cwd(home, tmp_path):
    salvar_escopo(home, tmp_path / "cakto")
    (tmp_path / "cakto").mkdir()
    env = {"CLAUDE_PROJECT_DIR": str(tmp_path / "cakto")}
    r = pre_tool_use(payload("renomeie a variável userId", cwd="/x"), home, env)
    assert "updatedInput" in r["hookSpecificOutput"]


def test_perfil_e_lido_a_cada_spawn(home):
    salvar_perfil(home, Perfil(economia=Economia.LOW))
    r = pre_tool_use(payload("renomeie a variável userId"), home, {})
    assert r["hookSpecificOutput"]["updatedInput"]["model"] == "sonnet"


def test_piso_do_repo_e_aplicado(home, tmp_path):
    (tmp_path / "cakto-downshift.json").write_text('{"versao": 1, "minimo_por_risco": {"dinheiro": "opus"}}')
    r = pre_tool_use(payload("formate a data do relatório de chargeback", modelo="sonnet", cwd=str(tmp_path)), home, {})
    assert r["hookSpecificOutput"]["updatedInput"]["model"] == "opus"
    assert ler(home)[-1]["piso_repo"] is True


@pytest.mark.parametrize("p", [{}, {"tool_input": {}}, {"tool_input": {"prompt": ""}}, {"tool_input": "nao e dict"}])
def test_payload_sem_tarefa_responde_vazio(home, p):
    assert pre_tool_use(p, home, {}) == {}
