import os
import sys
import tempfile
from pathlib import Path

# Os testes usam um diretório de dados temporário (config lê a variável na importação).
_TMP = tempfile.mkdtemp(prefix="eletrodiag-test-")
os.environ["ELETRODIAG_DATA"] = _TMP
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def pipeline_run():
    """Executa o pipeline completo (sem o passo 'app') com volumes reduzidos."""
    from eletrodiag.pipeline import config as C
    from eletrodiag.pipeline.run import STEPS, main

    steps = [s for s in STEPS if s != "app"]
    code = main(["--fresh", "--n-mc", "40", "--scenarios", "40", "--steps", *steps])
    return {"code": code, "data": C.DATA}
