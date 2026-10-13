import json

from cakto_downshift.escopo import salvar as salvar_escopo
from cakto_downshift.hooks.claude_code import post_tool_use, session_start, subagent_stop
from cakto_downshift.telemetria import ler


def test_session_start_entrega_orcamento_como_contexto(home):
    r = session_start({"session_id": "s", "cwd": "/tmp/p"}, home, {})
    ctx = r["hookSpecificOutput"]["additionalContext"]
    assert r["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "subagente" in ctx and "medium" in ctx
    assert ler(home)[-1]["tipo"] == "sessao"


def test_session_start_fora_do_escopo(home, tmp_path):
    salvar_escopo(home, tmp_path / "cakto")
    assert session_start({"cwd": str(tmp_path / "outro")}, home, {}) == {}


def test_subagent_stop_grava_uso_com_custo(home, tmp_path):
    t = tmp_path / "a.jsonl"
    t.write_text(json.dumps({"type": "assistant", "message": {"model": "claude-haiku-5-5",
                 "usage": {"input_tokens": 1_000_000, "output_tokens": 0}}}) + "\n")
    assert subagent_stop({"session_id": "s", "agent_id": "a1", "agent_transcript_path": str(t), "cwd": "/tmp/p"}, home, {}) == {}
    ev = ler(home)[-1]
    assert ev["tipo"] == "uso" and ev["modelo"] == "haiku" and ev["entrada"] == 1_000_000
    assert abs(ev["custo_usd"] - 0.10) < 1e-9


def test_subagent_stop_sem_transcript_grava_zeros(home):
    subagent_stop({"session_id": "s", "agent_id": "a1", "cwd": "/tmp/p"}, home, {})
    ev = ler(home)[-1]
    assert ev["tipo"] == "uso" and ev["entrada"] == 0 and ev["modelo"] is None and ev["transcript"] == "sem_caminho"


def test_subagent_stop_diz_por_que_o_uso_veio_zerado(home, tmp_path):
    # Filho interno do Claude Code chega com caminho que não existe; arquivo sem resposta é "vazio".
    subagent_stop({"session_id": "s", "agent_id": "a1", "agent_transcript_path": str(tmp_path / "nao.jsonl"), "cwd": "/tmp/p"}, home, {})
    assert ler(home)[-1]["transcript"] == "ausente"
    vazio = tmp_path / "v.jsonl"
    vazio.write_text(json.dumps({"type": "user", "message": {"content": "x"}}) + "\n")
    subagent_stop({"session_id": "s", "agent_id": "a2", "agent_transcript_path": str(vazio), "cwd": "/tmp/p"}, home, {})
    assert ler(home)[-1]["transcript"] == "vazio" and ler(home)[-1]["modelo"] is None


def test_post_tool_use_grava_resultado(home):
    # Formato real do Claude Code 2.1.x: o modelo vem em resolvedModel, e agentId casa com o SubagentStop.
    real = {"agentId": "ag1", "resolvedModel": "claude-haiku-5-5", "status": "completed", "description": "x", "prompt": "..."}
    base = {"session_id": "s", "tool_use_id": "t1", "cwd": "/tmp/p", "tool_name": "Task", "tool_response": real}
    assert post_tool_use({**base, "hook_event_name": "PostToolUse"}, home, {}) == {}
    assert post_tool_use({**base, "hook_event_name": "PostToolUseFailure", "tool_response": "erro"}, home, {}) == {}
    assert post_tool_use({**base, "hook_event_name": "PostToolUse", "tool_response": {**real, "status": "async_launched"}}, home, {}) == {}
    assert post_tool_use({**base, "hook_event_name": "PostToolUse", "tool_response": {"model": "claude-sonnet-5-5"}}, home, {}) == {}
    evs = [e for e in ler(home) if e["tipo"] == "resultado"]
    assert evs[0]["modelo_reportado"] == "haiku" and evs[0]["status"] == "concluido" and evs[0]["agent_id"] == "ag1"
    assert evs[1]["modelo_reportado"] is None and evs[1]["status"] == "erro" and evs[1]["agent_id"] is None
    assert evs[2]["status"] == "em_andamento"
    assert evs[3]["modelo_reportado"] == "sonnet" and evs[3]["status"] == "desconhecido"
    post_tool_use({**base, "tool_name": "Bash"}, home, {})
    assert len([e for e in ler(home) if e["tipo"] == "resultado"]) == 4


def test_subagent_stop_tolera_tipos_errados(home, tmp_path):
    subagent_stop({"session_id": "s", "agent_id": {"x": 1}, "agent_transcript_path": str(tmp_path), "cwd": "/tmp/p"}, home, {})
    ev = ler(home)[-1]
    assert ev["agent_id"] is None and ev["entrada"] == 0 and ev["saida"] == 0 and ev["modelo"] is None


def test_post_tool_use_ignora_tool_use_id_nao_string(home):
    post_tool_use({"session_id": "s", "tool_use_id": 7, "cwd": "/tmp/p", "tool_name": "Task",
                   "hook_event_name": "PostToolUse"}, home, {})
    assert ler(home)[-1]["tool_use_id"] is None
