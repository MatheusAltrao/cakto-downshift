import json
from datetime import datetime, timedelta, timezone

from cakto_downshift.telemetria import gravar, hash_sessao, ler, nome_projeto


def test_hash_sessao_estavel_e_curto():
    assert hash_sessao("abc") == hash_sessao("abc") and len(hash_sessao("abc")) == 16
    assert hash_sessao(None) is None


def test_gravar_cria_com_modo_e_ler_filtra_por_data(home):
    gravar(home, {"tipo": "decisao", "classe": "mecanica"})
    antigo = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    gravar(home, {"tipo": "uso", "ts": antigo})
    assert oct((home / "eventos.jsonl").stat().st_mode & 0o777) == "0o600"
    todos = ler(home)
    assert [e["tipo"] for e in todos] == ["decisao", "uso"] and "ts" in todos[0]
    recentes = ler(home, desde=datetime.now(timezone.utc) - timedelta(days=7))
    assert [e["tipo"] for e in recentes] == ["decisao"]


def test_gravar_nunca_lanca(tmp_path):
    arquivo_no_lugar_da_pasta = tmp_path / "x"
    arquivo_no_lugar_da_pasta.write_text("")
    gravar(arquivo_no_lugar_da_pasta, {"tipo": "falha"})  # não pode lançar


def test_ler_ignora_linha_corrompida(home):
    gravar(home, {"tipo": "a"})
    with (home / "eventos.jsonl").open("a") as f:
        f.write("{corrompida\n")
    assert [e["tipo"] for e in ler(home)] == ["a"]


def test_nome_projeto():
    assert nome_projeto("/home/x/trabalho/cakto/cakto-backend") == "cakto-backend"
    assert nome_projeto(None) is None
