import json

from cakto_downshift.transcript import Uso, modelo_da_sessao, modelo_do_transcript, uso_do_transcript


def linha(tipo, modelo=None, usage=None):
    msg = {"role": tipo}
    if modelo:
        msg["model"] = modelo
    if usage:
        msg["usage"] = usage
    return json.dumps({"type": tipo, "message": msg})


def test_modelo_da_sessao_e_o_da_ultima_assistant_nao_sintetica(tmp_path):
    t = tmp_path / "s.jsonl"
    t.write_text("\n".join([
        linha("user"), linha("assistant", "claude-opus-5-5"), linha("user"),
        linha("assistant", "<synthetic>"),
    ]))
    assert modelo_da_sessao(t) == "claude-opus-5-5"


def test_modelo_da_sessao_ausente_ou_ilegivel(tmp_path):
    assert modelo_da_sessao(tmp_path / "nao-existe.jsonl") is None
    t = tmp_path / "lixo.jsonl"
    t.write_text("isto nao e json\n{\n")
    assert modelo_da_sessao(t) is None


def test_uso_soma_todas_as_assistant(tmp_path):
    t = tmp_path / "a.jsonl"
    t.write_text("\n".join([
        linha("assistant", "claude-haiku-5-5", {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 7}),
        linha("assistant", "claude-haiku-5-5", {"input_tokens": 1, "output_tokens": 2}),
        linha("user"),
    ]))
    assert uso_do_transcript(t) == Uso(11, 7, 100, 7)
    assert modelo_do_transcript(t) == "claude-haiku-5-5"
    assert uso_do_transcript(tmp_path / "x") == Uso(0, 0, 0, 0)


def test_usage_malformado_nao_aborta_a_soma(tmp_path):
    t = tmp_path / "m.jsonl"
    t.write_text("\n".join([
        json.dumps({"type": "assistant", "message": {"model": "claude-haiku-5-5", "usage": "x"}}),
        json.dumps({"type": "assistant", "message": {"model": "claude-haiku-5-5", "usage": {"input_tokens": "abc", "output_tokens": None}}}),
        linha("assistant", "claude-haiku-5-5", {"input_tokens": 4, "output_tokens": 6}),
    ]))
    assert uso_do_transcript(t) == Uso(4, 6, 0, 0)


def test_linha_json_que_nao_e_objeto_e_ignorada(tmp_path):
    t = tmp_path / "n.jsonl"
    t.write_text("\n".join([
        '["assistant"]',
        '"assistant"',
        linha("assistant", "claude-haiku-5-5", {"input_tokens": 3, "output_tokens": 1}),
        '"assistant" 1',
    ]))
    assert uso_do_transcript(t) == Uso(3, 1, 0, 0)
    assert modelo_da_sessao(t) == "claude-haiku-5-5"


def test_separador_unicode_dentro_de_string_nao_quebra_a_linha(tmp_path):
    # Linha escrita à mão: json.dumps (ensure_ascii=True) escaparia o U+2028 e o arquivo
    # não teria o caractere cru. Aqui o   da fonte Python vira o caractere real na string.
    t = tmp_path / "u.jsonl"
    linha_crua = ('{"type": "assistant", "message": {"model": "claude-haiku-5-5", '
                  '"content": "a b", "usage": {"input_tokens": 5, "output_tokens": 1}}}')
    assert " " in linha_crua
    t.write_text(linha_crua + "\n", encoding="utf-8")
    assert uso_do_transcript(t) == Uso(5, 1, 0, 0)


def test_modelo_da_sessao_com_cauda_cortada_dentro_de_linha_assistant(tmp_path, monkeypatch):
    import cakto_downshift.transcript as tr
    # X é uma linha assistant longa e a cauda começa no meio dela, em '"assistant"': o
    # fragmento é JSON inválido e tem de ser descartado sem exceção. Y é a última resposta.
    x = ('{"type": "assistant", "message": {"model": "claude-sonnet-5-5", '
         '"content": "' + "x" * 200 + '"}}\n')
    y = linha("assistant", "claude-opus-5-5") + "\n"
    arquivo = x + y
    pos = x.index('"assistant"')
    monkeypatch.setattr(tr, "CAUDA_BYTES", len(arquivo) - pos)
    t = tmp_path / "c.jsonl"
    t.write_text(arquivo, encoding="utf-8")
    assert modelo_da_sessao(t) == "claude-opus-5-5"


def test_modelo_da_sessao_so_synthetic_devolve_none(tmp_path):
    t = tmp_path / "s2.jsonl"
    t.write_text(linha("assistant", "<synthetic>") + "\n")
    assert modelo_da_sessao(t) is None


def test_modelo_do_transcript_escolhe_o_mais_frequente(tmp_path):
    t = tmp_path / "f.jsonl"
    t.write_text("\n".join([
        linha("assistant", "claude-haiku-5-5"),
        linha("assistant", "claude-opus-5-5"),
        linha("assistant", "claude-opus-5-5"),
        linha("assistant", "claude-haiku-5-5"),
        linha("assistant", "claude-opus-5-5"),
    ]))
    assert modelo_do_transcript(t) == "claude-opus-5-5"
