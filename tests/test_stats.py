from datetime import datetime, timedelta, timezone

from cakto_downshift.stats import formatar, ligar, resumo


def ts(minutos):
    return (datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=minutos)).isoformat()


def decisao(m, sessao="s", escrita="haiku", atual="opus", tool="t", motivos=("CLASSE_CONFIANTE",)):
    return {"tipo": "decisao", "ts": ts(m), "sessao": sessao, "tool_use_id": tool, "classe": "mecanica",
            "tier": "haiku", "familia_escrita": escrita, "familia_atual": atual, "motivos": list(motivos)}


def uso(m, sessao="s", modelo="haiku", entrada=1_000_000, saida=0):
    return {"tipo": "uso", "ts": ts(m), "sessao": sessao, "agent_id": "a", "modelo": modelo,
            "entrada": entrada, "saida": saida, "cache_leitura": 0, "cache_escrita": 0, "custo_usd": 0.10}


def test_ligacao_por_ordem_na_mesma_sessao():
    evs = [decisao(0, tool="t1"), decisao(1, tool="t2"), uso(2), uso(3), uso(4, sessao="outra")]
    ligados = [e for e in ligar(evs) if e["tipo"] == "uso"]
    assert [u["decisao"]["tool_use_id"] if u["ligacao"] else None for u in ligados] == ["t2", "t1", None]


def test_janela_de_duas_horas():
    evs = [decisao(0), uso(150)]
    assert ligar(evs)[1]["ligacao"] is None


def test_resumo_economia_so_com_ligacao():
    evs = [decisao(0), uso(1),
           {"tipo": "resultado", "ts": ts(1), "sessao": "s", "tool_use_id": "t", "modelo_reportado": "haiku", "status": "concluido"},
           decisao(5, escrita=None, motivos=("CLASSE_SEM_CONFIANCA", "GUARDA_SEM_CONFIANCA"))]
    r = resumo(evs)
    assert r["decisoes"] == 2 and r["escritas"] == 1 and r["confirmadas"] == 1
    assert r["seguradas_por_motivo"] == {"GUARDA_SEM_CONFIANCA": 1}
    assert r["usos"] == 1 and r["usos_ligados"] == 1
    # 1M tokens de entrada: opus 4.00 − haiku 0.10
    assert abs(r["economia_estimada_usd"] - 3.90) < 1e-6 and not r["sem_dado"]


def test_resumo_sem_dado():
    r = resumo([decisao(0)])
    assert r["sem_dado"] and r["economia_estimada_usd"] is None
    assert "não é fatura" in formatar(r, 7) and "sem dado" in formatar(r, 7)


def test_telemetria_malformada_nao_derruba():
    sem_ts = decisao(0)
    del sem_ts["ts"]
    ruim = uso(1)
    ruim.update(entrada=None, custo_usd="x")
    estranha = decisao(2, tool="t9", motivos=())
    estranha.update(motivos=None, classe={"a": 1})
    sem_sessao_d, sem_sessao_u = decisao(3), uso(4)
    del sem_sessao_d["sessao"], sem_sessao_u["sessao"]
    ingenuo = uso(5)
    ingenuo["ts"] = "2026-10-12T12:05:00"
    evs = [sem_ts, ruim, [1], "x", estranha, sem_sessao_d, sem_sessao_u, ingenuo, {"ts": "lixo", "tipo": "uso", "sessao": "s"}]
    r = resumo(evs)
    # só ingenuo (ts sem fuso, lido como UTC) liga, com estranha; os demais usos ficam sem par.
    assert r["usos"] == 4 and r["usos_ligados"] == 1
    assert r["por_classe"].get("desconhecido") == 1
    assert formatar(r, 7).endswith("não é fatura.")
