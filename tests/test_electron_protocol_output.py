from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_native_stdout_is_kept_out_of_the_electron_json_protocol():
    project_root = Path(__file__).resolve().parents[1]
    script = """
import os
from main import electron_protocol_output

with electron_protocol_output(True) as protocol:
    os.write(1, b'native-library-log\\n')
    protocol.write('{\"type\":\"ready\"}\\n')
    protocol.flush()
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == '{"type":"ready"}\n'
    assert "native-library-log" in result.stderr
