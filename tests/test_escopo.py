import os

from cakto_downshift.escopo import carregar, dentro, salvar


def test_salvar_carregar(home, tmp_path):
    salvar(home, tmp_path)
    assert carregar(home) == tmp_path.resolve()


def test_sem_escopo_tudo_entra(tmp_path):
    assert dentro(tmp_path, None) is True


def test_prefixo_por_componente_e_symlink(tmp_path):
    escopo = tmp_path / "cakto"
    (escopo / "repo").mkdir(parents=True)
    (tmp_path / "cakto-x").mkdir()
    os.symlink(escopo, tmp_path / "link")
    assert dentro(escopo / "repo", escopo)
    assert dentro(escopo, escopo)
    assert not dentro(tmp_path / "cakto-x", escopo)
    assert dentro(tmp_path / "link" / "repo", escopo)
    assert not dentro(None, escopo)
