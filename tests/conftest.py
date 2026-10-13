import pytest


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Pasta de estado isolada: nenhum teste toca ~/.cakto-downshift."""
    pasta = tmp_path / "estado"
    monkeypatch.setenv("CAKTO_DOWNSHIFT_HOME", str(pasta))
    return pasta
