import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse


APP_NAME = "pq-app-backend"
DEFAULT_ENGINE_MODULE = "pq_engine.cli"  # frozen engine entrypoint module
RESULTS_FILENAME = "results.json"

# Storage defaults to a folder in the backend directory (OK for local + MVP).
# For production durability, switch STORAGE_DIR to an attached disk or object storage.
DEFAULT_STORAGE_DIR = Path(__file__).resolve().parent / "storage"


app = FastAPI(title=APP_NAME, version="0.1.1")

# CORS: set CORS_ORIGINS="https://your-frontend-domain.com,https://another.com"
cors_env = os.getenv("CORS_ORIGINS", "")
if cors_env.strip():
    origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
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
    return name or "file"


def _storage_dir() -> Path:
    p = os.getenv("STORAGE_DIR", "").strip()
    base = Path(p) if p else DEFAULT_STORAGE_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def _run_dir(run_id: str) -> Path:
    d = _storage_dir() / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_engine(config_path: Path, out_dir: Path) -> subprocess.CompletedProcess:
    """
    Runs the frozen engine CLI via python -m <module>.
    Uses the same interpreter as this server (sys.executable) so venv site-packages are available.
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
    )


def _copy_outputs(src_out_dir: Path, dst_run_dir: Path) -> None:
    """
    Copy everything produced by the engine into persistent storage for the run.
    """
    for item in src_out_dir.iterdir():
        target = dst_run_dir / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


@app.get("/api/runs/{run_id}/results")
def get_results(run_id: str):
    rp = _run_dir(run_id) / RESULTS_FILENAME
    if not rp.exists():
        raise HTTPException(status_code=404, detail="Run results not found.")
    try:
        return JSONResponse(content=json.loads(rp.read_text(encoding="utf-8")))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse stored results.json: {e}")


@app.get("/api/runs/{run_id}/files/{filename}")
def get_file(run_id: str, filename: str):
    filename = _safe_filename(filename)
    p = _run_dir(run_id) / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found for this run.")
    # Let FastAPI infer content-type; FileResponse handles streaming efficiently.
    return FileResponse(path=str(p), filename=filename)


@app.post("/api/analyze")
async def analyze(config: UploadFile = File(...)):
    """
    Input: multipart/form-data field 'config' (YAML)
    Runs engine and returns results.json verbatim (no reshaping).

    Also persists all artifacts (results.json, report.html, pngs) under:
        STORAGE_DIR/<run_id>/

    Response header:
        X-Run-Id: <run_id>
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

    run_id = str(uuid.uuid4())
    dst_run_dir = _run_dir(run_id)

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

            # Persist artifacts before responding
            _copy_outputs(out_dir, dst_run_dir)

            try:
                results_obj = json.loads(results_path.read_text(encoding="utf-8"))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to parse results.json: {e}")

            resp = JSONResponse(content=results_obj)
            resp.headers["X-Run-Id"] = run_id
            return resp

    except HTTPException:
        # On errors, clean up the run dir so storage doesn't fill with failed runs
        if dst_run_dir.exists():
            shutil.rmtree(dst_run_dir, ignore_errors=True)
        raise
    except Exception as e:
        if dst_run_dir.exists():
            shutil.rmtree(dst_run_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {e}")
