"""Resumo da telemetria. Economia só aparece quando um uso está ligado a uma decisão; o resto é
contagem. A ligação é por agente quando o `resultado` trouxe o agentId, senão por ordem dentro
da sessão, e o resumo diz quantas foram de cada jeito."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from cakto_downshift.catalogo import custo_usd, por_familia

JANELA_LIGACAO = timedelta(hours=2)


def _dt(ev):
    # Evento vem de arquivo gravado por hook: ts ausente, ruim ou sem fuso não pode derrubar o comando.
    try:
        d = datetime.fromisoformat(ev["ts"])
    except (KeyError, TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _num(valor) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return 0.0
    return float(valor)


def _chave(valor) -> str:
    return valor if isinstance(valor, str) else "desconhecido"


def _dedupe_usos(eventos: list[dict]) -> list[dict]:
    """O SubagentStop pode disparar mais de uma vez pro mesmo filho (o agente para, é retomado e
    para de novo), e o transcript é cumulativo: vale o último uso de cada agente na sessão."""
    ultimo: dict[tuple, dict] = {}
    saida = []
    for ev in eventos:
        if ev.get("tipo") == "uso" and isinstance(ev.get("agent_id"), str) and ev.get("sessao") is not None:
            chave = (ev["sessao"], ev["agent_id"])
            if chave in ultimo:
                saida.remove(ultimo[chave])
            ultimo[chave] = ev
        saida.append(ev)
    return saida


def ligar(eventos: list[dict]) -> list[dict]:
    ordenados = _dedupe_usos(sorted(eventos, key=lambda e: str(e.get("ts") or "")))
    livres: dict[str, list[dict]] = defaultdict(list)
    por_tool: dict[tuple, dict] = {}
    por_agente: dict[tuple, dict] = {}
    for ev in ordenados:
        tempo = _dt(ev)
        if ev.get("tipo") == "decisao":
            if tempo is not None and ev.get("sessao") is not None:
                livres[ev["sessao"]].append(ev)
                if isinstance(ev.get("tool_use_id"), str):
                    por_tool[(ev["sessao"], ev["tool_use_id"])] = ev
        elif ev.get("tipo") == "resultado":
            if ev.get("sessao") is not None and isinstance(ev.get("agent_id"), str) and isinstance(ev.get("tool_use_id"), str):
                d = por_tool.get((ev["sessao"], ev["tool_use_id"]))
                if d is not None:
                    por_agente[(ev["sessao"], ev["agent_id"])] = d
        elif ev.get("tipo") == "uso":
            ev["ligacao"], ev["decisao"] = None, None
            if tempo is None or ev.get("sessao") is None:
                continue
            # Uso sem modelo é transcript ausente ou vazio: ligar a uma decisão gastaria a decisão
            # com custo zero e faria a economia parecer total.
            if not isinstance(ev.get("modelo"), str):
                continue
            candidatos = livres.get(ev["sessao"], [])
            # Caminho determinístico: uso.agent_id → resultado.agent_id → resultado.tool_use_id → decisão.
            d = por_agente.get((ev["sessao"], ev["agent_id"])) if isinstance(ev.get("agent_id"), str) else None
            if d is not None and d in candidatos:
                ev["ligacao"], ev["decisao"] = "agente", d
                candidatos.remove(d)
                continue
            # A decisão mais recente da sessão ainda sem uso: com filhos em paralelo pode trocar as pontas.
            for d in reversed(candidatos):
                if tempo - _dt(d) <= JANELA_LIGACAO:
                    ev["ligacao"], ev["decisao"] = "ordem", d
                    candidatos.remove(d)
                    break
    return ordenados


def _custo(familia, u):
    m = por_familia(familia) if familia else None
    if not m:
        return None
    return custo_usd(m, _num(u.get("entrada")), _num(u.get("saida")), _num(u.get("cache_leitura")), _num(u.get("cache_escrita")))


def resumo(eventos: list[dict]) -> dict:
    evs = ligar([dict(e) for e in eventos if isinstance(e, dict)])
    decisoes = [e for e in evs if e.get("tipo") == "decisao"]
    usos = [e for e in evs if e.get("tipo") == "uso"]
    resultados = {e["tool_use_id"]: e for e in evs if e.get("tipo") == "resultado" and e.get("tool_use_id") is not None}
    escritas = [d for d in decisoes if d.get("familia_escrita")]
    confirmadas = sum(1 for d in escritas if d.get("tool_use_id") is not None
                      and (r := resultados.get(d["tool_use_id"])) and r.get("modelo_reportado") == d["familia_escrita"])
    seguradas = Counter(m for d in decisoes if not d.get("familia_escrita") and isinstance(d.get("motivos"), list)
                        for m in d["motivos"] if isinstance(m, str) and m.startswith("GUARDA_"))
    custo_tier: dict[str, float] = defaultdict(float)
    custo_sessao: dict[str, float] = defaultdict(float)
    for u in usos:
        custo = _num(u.get("custo_usd"))
        custo_tier[_chave(u.get("modelo"))] += custo
        custo_sessao[u.get("sessao") or "?"] += custo
    ligados = [u for u in usos if u["ligacao"]]
    por_ligacao = Counter(u["ligacao"] for u in ligados)
    sem_transcript = Counter(_chave(u.get("transcript")) for u in usos if not isinstance(u.get("modelo"), str))
    economia = None
    for u in ligados:
        d = u["decisao"]
        if d.get("familia_escrita") and d.get("familia_atual"):
            real, herdado = _custo(d["familia_escrita"], u), _custo(d["familia_atual"], u)
            if real is not None and herdado is not None:
                economia = (economia or 0.0) + (herdado - real)
    return {
        "decisoes": len(decisoes),
        "por_classe": dict(Counter(_chave(d.get("classe")) for d in decisoes)),
        "por_tier": dict(Counter(_chave(d.get("tier")) for d in decisoes)),
        "escritas": len(escritas), "confirmadas": confirmadas,
        "seguradas_por_motivo": dict(seguradas),
        "usos": len(usos), "usos_ligados": len(ligados), "usos_por_ligacao": dict(por_ligacao),
        "usos_sem_modelo": dict(sem_transcript),
        "custo_por_tier": dict(custo_tier),
        "custo_por_sessao": {"sessoes": len(custo_sessao), "maximo": max(custo_sessao.values(), default=0.0),
                             "media": (sum(custo_sessao.values()) / len(custo_sessao)) if custo_sessao else 0.0},
        "economia_estimada_usd": economia,
        "sem_dado": not ligados,
    }


def formatar(r: dict, dias: int) -> str:
    linhas = [f"Últimos {dias} dias", f"decisões: {r['decisoes']}  por classe: {r['por_classe']}  por tier: {r['por_tier']}",
              f"reescritas: {r['escritas']} (confirmadas pelo Claude Code: {r['confirmadas']})",
              f"seguradas por motivo: {r['seguradas_por_motivo'] or 'nenhuma'}",
              f"usos gravados: {r['usos']}, ligados a uma decisão: {r['usos_ligados']} (por agente: {r['usos_por_ligacao'].get('agente', 0)}, por ordem: {r['usos_por_ligacao'].get('ordem', 0)})",
              f"usos sem modelo (transcript do filho): {r['usos_sem_modelo'] or 'nenhum'}",
              f"custo real por tier (USD): {{{', '.join(f'{k}: {v:.4f}' for k, v in r['custo_por_tier'].items())}}}",
              f"custo por sessão: {r['custo_por_sessao']['sessoes']} sessões, média {r['custo_por_sessao']['media']:.4f}, máximo {r['custo_por_sessao']['maximo']:.4f}"]
    if r["sem_dado"]:
        linhas.append("economia: sem dado (nenhum uso ligado a uma decisão)")
    else:
        linhas.append(f"economia estimada: {r['economia_estimada_usd']:.4f} USD")
    linhas.append("Custos estimados pelo catálogo, não é fatura.")
    return "\n".join(linhas)
