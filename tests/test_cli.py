import subprocess
import sys

from cakto_downshift import __version__
from cakto_downshift.cli import main


def test_version_flag_imprime_versao(capsys):
    assert main(["--version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_entry_point_instalado_responde():
    saida = subprocess.run(
        [sys.executable, "-m", "cakto_downshift.cli", "--version"],
        capture_output=True, text=True, check=True,
    )
    assert __version__ in saida.stdout
