"""Os hooks do Claude Code. Cada função recebe o payload já decodificado e devolve o dict de
resposta. `executar` é a borda: stdin, stdout, e a regra de que nada aqui derruba um spawn."""
import json
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import IO

from cakto_downshift import escopo as mod_escopo
from cakto_downshift import perfil as mod_perfil
from cakto_downshift import telemetria
from cakto_downshift.catalogo import custo_usd, familia_de, por_familia
from cakto_downshift.piso import carregar_do_projeto
from cakto_downshift.politica import Entrada, decidir
from cakto_downshift.transcript import modelo_da_sessao, modelo_do_transcript, uso_do_transcript

MAX_BYTES = 1024 * 1024
NOMES = ("pre-tool-use", "session-start", "subagent-stop", "post-tool-use")
# Limita o custo em prompts enormes: a intenção e os sinais de risco aparecem no começo.
MAX_TEXTO_CLASSIFICADO = 16 * 1024


def home_de(env: Mapping[str, str]) -> Path:
    return Path(env.get("CAKTO_DOWNSHIFT_HOME") or Path.home() / ".cakto-downshift")


def raiz_do_projeto(payload: dict, env: Mapping[str, str]) -> Path | None:
    raiz = env.get("CLAUDE_PROJECT_DIR") or payload.get("cwd")
    return Path(raiz) if isinstance(raiz, str) and raiz else None


def _texto_da_tarefa(payload: dict) -> str | None:
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return None
    for campo in ("prompt", "description"):
        # Campo presente com tipo errado é payload fora do contrato: vira falha registrada, não silêncio.
        if campo in ti and not isinstance(ti[campo], str):
            raise ValueError("CAMPO_INVALIDO")
        if isinstance(ti.get(campo), str) and ti[campo].strip():
            return ti[campo]
    return None


def _modelo_atual(payload: dict) -> str | None:
    ti = payload["tool_input"]
    modelo = ti.get("model") if isinstance(ti.get("model"), str) else None
    if not modelo and isinstance(payload.get("transcript_path"), str):
        modelo = modelo_da_sessao(Path(payload["transcript_path"]))
    return familia_de(modelo)


def pre_tool_use(payload: dict, home: Path, env: Mapping[str, str]) -> dict:
    inicio = time.perf_counter()
    raiz = raiz_do_projeto(payload, env)
    if not mod_escopo.dentro(raiz, mod_escopo.carregar(home)):
        return {}
    texto = _texto_da_tarefa(payload)
    if texto is None:
        return {}
    ti = payload["tool_input"]
    if "subagent_type" in ti and not isinstance(ti["subagent_type"], str):
        raise ValueError("CAMPO_INVALIDO")
    agente = ti.get("subagent_type") or ""
    perfil = mod_perfil.carregar(home)
    piso, _ = carregar_do_projeto(raiz) if raiz else (None, None)
    d = decidir(Entrada(
        texto=texto[:MAX_TEXTO_CLASSIFICADO], familia_atual=_modelo_atual(payload), agente=agente,
        perfil=perfil, piso=piso,
        rotear_nomeados=env.get("CAKTO_DOWNSHIFT_ROTEAR_NOMEADOS") == "1",
        modelo_na_chamada=isinstance(ti.get("model"), str) and bool(ti["model"]),
    ))
    telemetria.gravar(home, {
        "tipo": "decisao",
        "sessao": telemetria.hash_sessao(payload.get("session_id")),
        "tool_use_id": payload["tool_use_id"] if isinstance(payload.get("tool_use_id"), str) else None,
        "agente": agente or "general-purpose",
        "projeto": telemetria.nome_projeto(str(raiz) if raiz else None),
        "classe": d.classe.name.lower(), "confianca": d.confianca,
        "risco": sorted(r.value for r in d.riscos), "perfil": perfil.economia.value,
        "piso_repo": d.piso_repo, "piso_perfil": d.piso_perfil,
        "tier": d.tier.name.lower(), "familia_atual": d.familia_atual, "familia_escrita": d.familia_escrita,
        "motivos": list(d.motivos), "ms": round((time.perf_counter() - inicio) * 1000, 1),
    })
    if d.familia_escrita is None:
        return {}
    # O Claude Code só aplica updatedInput junto de uma decisão; por isso o allow fica só aqui.
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "allow",
        "updatedInput": {**ti, "model": d.familia_escrita},
    }}


def session_start(payload: dict, home: Path, env: Mapping[str, str]) -> dict:
    if not mod_escopo.dentro(raiz_do_projeto(payload, env), mod_escopo.carregar(home)):
        return {}
    perfil = mod_perfil.carregar(home)
    orc = mod_perfil.orcamento(perfil, mod_perfil.ram_disponivel_gb())
    telemetria.gravar(home, {"tipo": "sessao", "sessao": telemetria.hash_sessao(payload.get("session_id")),
                             "orcamento": orc.maximo, "motivo": orc.motivo, "perfil": perfil.economia.value})
    # Um hook vê um spawn por vez e não decide quantos o modelo abre: o limite só pode ser contexto.
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": mod_perfil.orientacao(orc, perfil.economia)}}


def subagent_stop(payload: dict, home: Path, env: Mapping[str, str]) -> dict:
    if not mod_escopo.dentro(raiz_do_projeto(payload, env), mod_escopo.carregar(home)):
        return {}
    caminho = payload.get("agent_transcript_path")
    uso = uso_do_transcript(Path(caminho)) if isinstance(caminho, str) else None
    familia = familia_de(modelo_do_transcript(Path(caminho))) if isinstance(caminho, str) else None
    modelo = por_familia(familia) if familia else None
    custo = custo_usd(modelo, uso.entrada, uso.saida, uso.cache_leitura, uso.cache_escrita) if (modelo and uso) else None
    telemetria.gravar(home, {
        "tipo": "uso", "sessao": telemetria.hash_sessao(payload.get("session_id")),
        "agent_id": payload["agent_id"] if isinstance(payload.get("agent_id"), str) else None, "modelo": familia,
        "entrada": uso.entrada if uso else 0, "saida": uso.saida if uso else 0,
        "cache_leitura": uso.cache_leitura if uso else 0, "cache_escrita": uso.cache_escrita if uso else 0,
        "custo_usd": round(custo, 6) if custo is not None else None,
    })
    return {}


def post_tool_use(payload: dict, home: Path, env: Mapping[str, str]) -> dict:
    if payload.get("tool_name") not in ("Task", "Agent"):
        return {}
    if not mod_escopo.dentro(raiz_do_projeto(payload, env), mod_escopo.carregar(home)):
        return {}
    resposta = payload.get("tool_response")
    reportado = familia_de(resposta.get("model")) if isinstance(resposta, dict) else None
    telemetria.gravar(home, {
        "tipo": "resultado", "sessao": telemetria.hash_sessao(payload.get("session_id")),
        "tool_use_id": payload["tool_use_id"] if isinstance(payload.get("tool_use_id"), str) else None,
        "modelo_reportado": reportado,
        "status": "erro" if payload.get("hook_event_name") == "PostToolUseFailure" else "concluido",
    })
    return {}


_HOOKS = {"pre-tool-use": pre_tool_use, "session-start": session_start,
          "subagent-stop": subagent_stop, "post-tool-use": post_tool_use}


def executar(nome: str, entrada: IO[bytes], saida: IO[str], env: Mapping[str, str]) -> int:
    """Sempre exit 0 e sempre JSON na saída: um erro nosso nunca pode virar um spawn bloqueado."""
    home: Path | None = None
    resposta: dict = {}
    try:
        home = home_de(env)
        bruto = entrada.read(MAX_BYTES + 1)
        if len(bruto) > MAX_BYTES:
            raise ValueError("PAYLOAD_GRANDE")
        payload = json.loads(bruto)
        if not isinstance(payload, dict):
            raise ValueError("PAYLOAD_NAO_OBJETO")
        funcao = _HOOKS.get(nome)
        if funcao is None:
            raise ValueError("HOOK_DESCONHECIDO")
        resposta = funcao(payload, home, env)
    except Exception as e:  # noqa: BLE001 — fail-open é o contrato deste ponto
        codigo = str(e) if isinstance(e, ValueError) and str(e).isupper() else type(e).__name__
        if home is not None:
            telemetria.gravar(home, {"tipo": "falha", "hook": nome, "codigo": codigo})
        resposta = {}
    try:
        saida.write(json.dumps(resposta, ensure_ascii=False) + "\n")
        saida.flush()
    except (OSError, ValueError):
        # Pipe fechado: sem desviar o fd 1, o flush do shutdown do interpretador falha de novo (exit 120).
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError):
            pass
    return 0
