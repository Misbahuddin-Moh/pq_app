import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


APP_NAME = "pq-app-backend"
DEFAULT_ENGINE_MODULE = "pq_engine.cli"  # frozen engine entrypoint module
RESULTS_FILENAME = "results.json"

# Repo root (pq_app). This allows us to expose pq_app/examples to the engine via PYTHONPATH
APP_ROOT = Path(__file__).resolve().parents[1]


app = FastAPI(title=APP_NAME, version="0.1.0")

# CORS: set CORS_ORIGINS="https://your-frontend-domain.com,https://another.com"
cors_env = os.getenv("CORS_ORIGINS", "")
if cors_env.strip():
    origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    # Dev-friendly default (tighten in production with CORS_ORIGINS)
    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True, "service": APP_NAME}


def _safe_filename(name: str) -> str:
    name = name.replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_", ".", "+"))
    return name or "config.yaml"


def _compose_env_for_engine() -> dict:
    """
    Ensure engine can import 'examples.*' from pq_app/examples without changing engine code.
    We do this by injecting pq_app repo root into PYTHONPATH.
    """
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "").strip()
    parts = [str(APP_ROOT)]
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def _run_engine(config_path: Path, out_dir: Path) -> subprocess.CompletedProcess:
    """
    Runs the frozen engine CLI via python -m <module>.
    IMPORTANT: use the same interpreter as this server (sys.executable) so the venv
    site-packages (including pq-engine) are available.
    """
    engine_module = os.getenv("PQ_ENGINE_MODULE", DEFAULT_ENGINE_MODULE)
    python_bin = os.getenv("PYTHON_BIN", sys.executable)

    cmd = [
        python_bin,
        "-m",
        engine_module,
        "--config",
        str(config_path),
        "--out",
        str(out_dir),
    ]

    timeout_s: Optional[float] = None
    t = os.getenv("ENGINE_TIMEOUT_SECONDS", "").strip()
    if t:
        try:
            timeout_s = float(t)
        except ValueError:
            timeout_s = None

    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(out_dir),
        timeout=timeout_s,
        env=_compose_env_for_engine(),
    )


@app.post("/api/analyze")
async def analyze(config: UploadFile = File(...)):
    """
    Input: multipart/form-data field 'config' (YAML)
    Runs engine and returns outputs/results.json verbatim (no reshaping).
    """
    if not config.filename:
        raise HTTPException(status_code=400, detail="Missing filename for uploaded config.")

    filename = _safe_filename(config.filename)
    lower = filename.lower()
    if not (lower.endswith(".yml") or lower.endswith(".yaml")):
        raise HTTPException(status_code=400, detail="Config must be a .yml or .yaml file.")

    content = await config.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded config file is empty.")

    try:
        with tempfile.TemporaryDirectory(prefix="pq_run_") as td:
            run_dir = Path(td)
            out_dir = run_dir / "outputs"
            out_dir.mkdir(parents=True, exist_ok=True)

            config_path = run_dir / filename
            config_path.write_bytes(content)

            try:
                proc = _run_engine(config_path=config_path, out_dir=out_dir)
            except subprocess.TimeoutExpired:
                raise HTTPException(
                    status_code=504,
                    detail="Engine run timed out. Increase ENGINE_TIMEOUT_SECONDS or optimize inputs.",
                )

            results_path = out_dir / RESULTS_FILENAME

            if proc.returncode != 0:
                stdout = (proc.stdout or "")[-8000:]
                stderr = (proc.stderr or "")[-8000:]
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "Engine execution failed.",
                        "returncode": proc.returncode,
                        "stdout_tail": stdout,
                        "stderr_tail": stderr,
                    },
                )

            if not results_path.exists():
                stdout = (proc.stdout or "")[-8000:]
                stderr = (proc.stderr or "")[-8000:]
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "Engine did not produce results.json.",
                        "stdout_tail": stdout,
                        "stderr_tail": stderr,
                    },
                )

            try:
                results_obj = json.loads(results_path.read_text(encoding="utf-8"))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to parse results.json: {e}")

            return JSONResponse(content=results_obj)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {e}")
