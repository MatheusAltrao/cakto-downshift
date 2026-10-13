import json
import subprocess
import sys
import time

import pytest

from cakto_downshift.telemetria import ler


def rodar(nome, entrada: bytes, home):
    return subprocess.run(
        [sys.executable, "-m", "cakto_downshift.cli", "hook", nome],
        input=entrada, capture_output=True, timeout=10,
        env={"CAKTO_DOWNSHIFT_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )


def test_pre_tool_use_ponta_a_ponta(home):
    p = {"session_id": "s", "cwd": "/tmp/p", "tool_name": "Task", "tool_use_id": "t",
         "tool_input": {"prompt": "renomeie a variável userId para customerId", "model": "claude-opus-5-5", "subagent_type": "general-purpose"}}
    r = rodar("pre-tool-use", json.dumps(p).encode(), home)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["hookSpecificOutput"]["updatedInput"]["model"] == "haiku"


@pytest.mark.parametrize("entrada", [b"", b"{nao e json", b"[]", b"null", b'{"tool_input": {"prompt": 5}}'])
def test_entrada_invalida_e_fail_open(home, entrada):
    r = rodar("pre-tool-use", entrada, home)
    assert r.returncode == 0 and json.loads(r.stdout) == {}
    assert ler(home)[-1]["tipo"] == "falha"


def test_payload_acima_de_1mb_e_fail_open(home):
    p = {"tool_input": {"prompt": "x" * (1024 * 1024 + 10)}}
    r = rodar("pre-tool-use", json.dumps(p).encode(), home)
    assert r.returncode == 0 and json.loads(r.stdout) == {}


def test_nome_de_hook_desconhecido_e_fail_open(home):
    r = rodar("inexistente", b"{}", home)
    assert r.returncode == 0 and json.loads(r.stdout) == {}


def test_latencia(home):
    from cakto_downshift.hooks.claude_code import pre_tool_use
    p = {"session_id": "s", "cwd": "/tmp/p", "tool_input": {"prompt": "renomeie a variável userId para customerId", "model": "claude-opus-5-5"}}
    inicio = time.perf_counter()
    for _ in range(200):
        pre_tool_use(p, home, {})
    assert (time.perf_counter() - inicio) / 200 < 0.150
    grande = {"tool_input": {"prompt": "renomeie " * 100_000, "model": "claude-opus-5-5"}}
    inicio = time.perf_counter()
    pre_tool_use(grande, home, {})
    assert time.perf_counter() - inicio < 0.5


def test_stdout_fechado_nao_derruba_o_hook(home):
    p = {"session_id": "s", "cwd": "/tmp/p", "tool_input": {"prompt": "renomeie a variável userId", "model": "claude-opus-5-5"}}
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(0.5); import sys; from cakto_downshift.cli import main; sys.exit(main(['hook','pre-tool-use']))"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={"CAKTO_DOWNSHIFT_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    proc.stdout.close()
    proc.stdin.write(json.dumps(p).encode())
    proc.stdin.close()
    err = proc.stderr.read()
    proc.stderr.close()
    assert proc.wait(timeout=10) == 0
    assert b"Traceback" not in err


def test_stdout_sem_utf8_ainda_entrega_a_reescrita(home):
    # O prompt ecoado tem acento e seta; com stdout em ASCII o write não pode perder a resposta.
    p = {"session_id": "s", "cwd": "/tmp/p", "tool_input": {"prompt": "renomeie a variável userId → customerId", "model": "claude-opus-5-5"}}
    r = subprocess.run(
        [sys.executable, "-m", "cakto_downshift.cli", "hook", "pre-tool-use"],
        input=json.dumps(p).encode(), capture_output=True, timeout=10,
        env={"CAKTO_DOWNSHIFT_HOME": str(home), "PATH": "/usr/bin:/bin", "PYTHONIOENCODING": "ascii"},
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["hookSpecificOutput"]["updatedInput"]["model"] == "haiku"


def test_stdin_fechado_no_arranque_e_fail_open(home):
    r = subprocess.run(
        ["/bin/sh", "-c", f'"{sys.executable}" -m cakto_downshift.cli hook pre-tool-use <&-'],
        capture_output=True, timeout=10, env={"CAKTO_DOWNSHIFT_HOME": str(home), "PATH": "/usr/bin:/bin"},
    )
    assert r.returncode == 0 and json.loads(r.stdout) == {} and b"Traceback" not in r.stderr
