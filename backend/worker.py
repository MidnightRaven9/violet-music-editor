"""Isolated worker that processes one audio file.

Run as a subprocess from backend.main so an OOM or crash in the audio pipeline
does not kill the API server.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make `backend` importable when this script is run as a subprocess.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.audio import process_file


def _progress_cb(pct: int, msg: str) -> None:
    print(json.dumps({"progress": pct, "message": msg}), flush=True)


def main() -> int:
    if len(sys.argv) < 7:
        print("Usage: worker.py <input> <output> <effect> <rate> <pitch> <reverb>", file=sys.stderr)
        return 1

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    effect = sys.argv[3]
    rate = float(sys.argv[4])
    pitch = float(sys.argv[5])
    reverb = float(sys.argv[6])

    try:
        process_file(input_path, output_path, effect, rate, pitch, reverb, _progress_cb)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
