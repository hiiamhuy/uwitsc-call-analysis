#!/bin/bash
# Lightweight health check for the Ollama container.

set -euo pipefail

OUT_DIR=${1:-.}
MODEL=${OLLAMA_MODEL:-deepseek-r1:32b}

mkdir -p "$OUT_DIR"

cleanup() {
    if [[ -n "${OLLAMA_PID:-}" ]]; then
        kill "$OLLAMA_PID" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

echo "Starting Ollama server..."
ollama serve >/tmp/ollama-start.log 2>&1 &
OLLAMA_PID=$!
sleep 3

echo "Waiting for Ollama to accept connections..."
python3 - "$MODEL" "$OUT_DIR/llama.err" "$OUT_DIR/llama.out" <<'PY'
import json
import os
import sys
import time
from pathlib import Path

import requests

model = sys.argv[1]
err_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])

base_url = "http://127.0.0.1:11434"
for attempt in range(60):
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=2)
        if resp.status_code == 200:
            break
    except requests.RequestException:
        time.sleep(1)
else:
    err_path.write_text("Timed out waiting for Ollama", encoding="utf-8")
    sys.exit(1)

payload = {
    "model": model,
    "prompt": "Respond with a short greeting.",
    "stream": False,
}
try:
    response = requests.post(f"{base_url}/api/generate", json=payload, timeout=30)
    response.raise_for_status()
except requests.RequestException as exc:
    err_path.write_text(str(exc), encoding="utf-8")
    sys.exit(1)

data = response.json()
out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
PY

echo "Ollama responded successfully. Details stored in $OUT_DIR/llama.out"
