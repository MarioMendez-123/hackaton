"""pytest -q — el reconocedor de comandos de voz (web/voice-commands.js) con
frases reales de Chrome y Edge. La prueba vive en voice_commands_check.js
porque el código es JavaScript; aquí solo se corre con node."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="necesita node instalado")
def test_comandos_de_voz_reconocen_frases_reales():
    result = subprocess.run(
        ["node", "voice_commands_check.js"],
        cwd=Path(__file__).parent,
        stdin=subprocess.DEVNULL,  # en Windows, sin esto falla con "handle is invalid"
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
