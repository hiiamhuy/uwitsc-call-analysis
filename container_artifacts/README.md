# Container build artifacts

Hyak login and compute nodes restrict outbound network access. To build the
Apptainer images defined in `whisperx_python.def` and `ollama_python.def`, place
all required offline assets in this directory structure before running
`apptainer build`.

```
container_artifacts/
├── whisperx/
│   ├── requirements.txt      # Python requirements list
│   └── wheels/                # Wheel files for torch, torchaudio, whisperx, etc.
└── ollama/
    ├── ollama-linux-amd64.tgz # Downloaded from https://ollama.com/download
    ├── requirements.txt       # Python requirements (e.g., requests)
    ├── wheels/                # Wheel cache satisfying requirements.txt
    └── models/                # Optional pre-loaded Ollama models directory
```

Populate `wheels/` with the exact wheel versions referenced in the respective
`requirements.txt` files. The build definitions install packages using
`pip --no-index --find-links` so that no network access is required during the
build process.

`models/` can contain a pre-exported Ollama model repository to avoid pulling
models at runtime. The directory is copied into the container at build time.
