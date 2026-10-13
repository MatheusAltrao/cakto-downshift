from cakto_downshift.classes import Classe, Tier
from cakto_downshift.perfil import Economia, Perfil
from cakto_downshift.piso import Piso
from cakto_downshift.politica import Entrada, decidir
from cakto_downshift.vocabulario_risco import Categoria

RENAME = "renomeie a variável userId para customerId"
SEM_SINAL = "faça aquilo que combinamos ontem"
COMPLEXA = "desenhe a arquitetura do serviço de notificações com fila e retentativa"
RISCO = "formate a data do relatório de chargeback"


def e(texto, atual="opus", agente="general-purpose", economia=Economia.MEDIUM, piso=None, **kw):
    return Entrada(texto, atual, agente, Perfil(economia=economia), piso, **kw)


def test_trivial_confiante_em_opus_escreve_haiku():
    d = decidir(e(RENAME))
    assert d.familia_escrita == "haiku" and "CLASSE_CONFIANTE" in d.motivos


def test_ja_no_tier_certo_nao_escreve():
    assert decidir(e(RENAME, atual="haiku")).familia_escrita is None


def test_sem_sinal_em_medium_fica():
    d = decidir(e(SEM_SINAL))
    assert d.familia_escrita is None and "GUARDA_SEM_CONFIANCA" in d.motivos and "SEM_SINAL" in d.motivos


def test_sem_sinal_em_high_desce_um_degrau():
    d = decidir(e(SEM_SINAL, economia=Economia.HIGH))
    assert d.familia_escrita == "sonnet" and "PERFIL_HIGH" in d.motivos
    assert d.tier == Tier.SONNET


def test_high_nunca_escreve_haiku_sem_confianca():
    d = decidir(e("escreva uma função " + "bem documentada e clara " * 15, economia=Economia.HIGH))
    assert d.classe <= Classe.SIMPLES and not d.confianca
    assert d.familia_escrita in (None, "sonnet")


def test_risco_sobe_para_sonnet_e_nunca_rebaixa():
    d = decidir(e(RISCO))
    assert Categoria.DINHEIRO in d.riscos and d.tier >= Tier.SONNET and not d.confianca
    assert d.familia_escrita is None and "GUARDA_RISCO" in d.motivos
    assert decidir(e(RISCO, economia=Economia.HIGH)).familia_escrita is None


def test_risco_em_sessao_haiku_sobe():
    d = decidir(e(RISCO, atual="haiku"))
    assert d.familia_escrita == "sonnet" and "PISO_RISCO" in d.motivos


def test_complexa_nunca_rebaixa_e_sobe_com_confianca():
    assert decidir(e(COMPLEXA, atual="opus")).familia_escrita is None
    d = decidir(e(COMPLEXA, atual="sonnet"))
    assert d.familia_escrita == "opus"


def test_agente_nomeado_sem_model_e_preservado():
    d = decidir(e(RENAME, agente="seguranca"))
    assert d.familia_escrita is None and "GUARDA_AGENTE_NOMEADO" in d.motivos
    assert decidir(e(RENAME, agente="seguranca", rotear_nomeados=True)).familia_escrita == "haiku"


def test_modelo_desconhecido_nao_escreve_em_nenhum_perfil():
    for economia in Economia:
        d = decidir(e(RENAME, atual=None, economia=economia))
        assert d.familia_escrita is None and "GUARDA_MODELO_DESCONHECIDO" in d.motivos


def test_low_nunca_escreve_haiku():
    d = decidir(e(RENAME, economia=Economia.LOW))
    assert d.familia_escrita == "sonnet" and d.piso_perfil and "PISO_PERFIL" in d.motivos
    assert decidir(e(RENAME, atual="sonnet", economia=Economia.LOW)).familia_escrita is None


def test_piso_repo_sobe_e_marca():
    piso = Piso(por_risco={Categoria.DINHEIRO: Tier.OPUS})
    d = decidir(e(RISCO, atual="sonnet", piso=piso))
    assert d.familia_escrita == "opus" and d.piso_repo and "PISO_REPO" in d.motivos


def test_fora_da_lista_nao_escreve():
    piso = Piso(minimo=Tier.FABLE)
    d = decidir(e(RENAME, atual="opus", piso=piso))
    assert d.familia_escrita is None and "GUARDA_FORA_DA_LISTA" in d.motivos
    p = Perfil(modelos=("haiku", "sonnet", "opus", "fable"))
    assert decidir(Entrada(RENAME, "opus", "general-purpose", p, piso)).familia_escrita == "fable"


def test_motivos_nao_carregam_texto():
    d = decidir(e(RENAME))
    assert all(m.isupper() or "_" in m for m in d.motivos)
    assert not any("userId" in m for m in d.motivos)


def test_complexa_confiante_nunca_rebaixa_de_fable_em_nenhum_perfil():
    modelos = ("haiku", "sonnet", "opus", "fable")
    for economia in Economia:
        p = Perfil(economia=economia, modelos=modelos)
        d = decidir(Entrada(COMPLEXA, "fable", "general-purpose", p))
        assert d.classe == Classe.COMPLEXA and d.confianca
        assert d.familia_escrita is None and "GUARDA_COMPLEXA" in d.motivos


def test_sem_confianca_nao_sobe_de_haiku():
    d = decidir(e(SEM_SINAL, atual="haiku"))
    assert d.familia_escrita is None and "GUARDA_SEM_CONFIANCA" in d.motivos


def test_piso_do_perfil_low_nao_destrava_subida_sem_confianca():
    d = decidir(e("escreva uma função " + "bem documentada e clara " * 15, atual="haiku", economia=Economia.LOW))
    assert d.classe <= Classe.SIMPLES and not d.confianca
    assert d.familia_escrita is None and "GUARDA_SEM_CONFIANCA" in d.motivos


def test_modelo_na_chamada_libera_agente_nomeado():
    d = decidir(e(RENAME, agente="seguranca", modelo_na_chamada=True))
    assert d.familia_escrita == "haiku"
