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
