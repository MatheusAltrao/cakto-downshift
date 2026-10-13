"""Resumo da telemetria. Economia só aparece quando um uso está ligado a uma decisão; o resto é
contagem. A ligação é por ordem dentro da sessão, e o resumo diz quantas foram assim."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from cakto_downshift.catalogo import custo_usd, por_familia

JANELA_LIGACAO = timedelta(hours=2)


def _dt(ev):
    return datetime.fromisoformat(ev["ts"])


def ligar(eventos: list[dict]) -> list[dict]:
    ordenados = sorted(eventos, key=lambda e: e.get("ts", ""))
    livres: dict[str, list[dict]] = defaultdict(list)
    for ev in ordenados:
        if ev.get("tipo") == "decisao":
            livres[ev.get("sessao")].append(ev)
        elif ev.get("tipo") == "uso":
            ev["ligacao"], ev["decisao"] = None, None
            candidatos = livres.get(ev.get("sessao"), [])
            # A decisão mais recente da sessão ainda sem uso: com filhos em paralelo pode trocar as pontas.
            for d in reversed(candidatos):
                if _dt(ev) - _dt(d) <= JANELA_LIGACAO:
                    ev["ligacao"], ev["decisao"] = "ordem", d
                    candidatos.remove(d)
                    break
    return ordenados


def _custo(familia, u):
    m = por_familia(familia) if familia else None
    return custo_usd(m, u["entrada"], u["saida"], u.get("cache_leitura", 0), u.get("cache_escrita", 0)) if m else None


def resumo(eventos: list[dict]) -> dict:
    evs = ligar([dict(e) for e in eventos])
    decisoes = [e for e in evs if e["tipo"] == "decisao"]
    usos = [e for e in evs if e["tipo"] == "uso"]
    resultados = {e.get("tool_use_id"): e for e in evs if e["tipo"] == "resultado"}
    escritas = [d for d in decisoes if d.get("familia_escrita")]
    confirmadas = sum(1 for d in escritas if (r := resultados.get(d.get("tool_use_id"))) and r.get("modelo_reportado") == d["familia_escrita"])
    seguradas = Counter(m for d in decisoes if not d.get("familia_escrita") for m in d.get("motivos", []) if m.startswith("GUARDA_"))
    custo_tier: dict[str, float] = defaultdict(float)
    custo_sessao: dict[str, float] = defaultdict(float)
    for u in usos:
        if u.get("custo_usd") is not None:
            custo_tier[u.get("modelo") or "desconhecido"] += u["custo_usd"]
            custo_sessao[u.get("sessao") or "?"] += u["custo_usd"]
    ligados = [u for u in usos if u["ligacao"]]
    economia = None
    for u in ligados:
        d = u["decisao"]
        if d.get("familia_escrita") and d.get("familia_atual"):
            real, herdado = _custo(d["familia_escrita"], u), _custo(d["familia_atual"], u)
            if real is not None and herdado is not None:
                economia = (economia or 0.0) + (herdado - real)
    return {
        "decisoes": len(decisoes),
        "por_classe": dict(Counter(d.get("classe") for d in decisoes)),
        "por_tier": dict(Counter(d.get("tier") for d in decisoes)),
        "escritas": len(escritas), "confirmadas": confirmadas,
        "seguradas_por_motivo": dict(seguradas),
        "usos": len(usos), "usos_ligados": len(ligados),
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
              f"usos gravados: {r['usos']}, ligados a uma decisão: {r['usos_ligados']} (ligação por ordem na sessão)",
              f"custo real por tier (USD): {{{', '.join(f'{k}: {v:.4f}' for k, v in r['custo_por_tier'].items())}}}",
              f"custo por sessão: {r['custo_por_sessao']['sessoes']} sessões, média {r['custo_por_sessao']['media']:.4f}, máximo {r['custo_por_sessao']['maximo']:.4f}"]
    if r["sem_dado"]:
        linhas.append("economia: sem dado (nenhum uso ligado a uma decisão)")
    else:
        linhas.append(f"economia estimada: {r['economia_estimada_usd']:.4f} USD")
    linhas.append("Custos estimados pelo catálogo, não é fatura.")
    return "\n".join(linhas)
