import os
import sys
import json
import uuid
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# -----------------------------
# App
# -----------------------------
app = FastAPI(title="pq-app-backend", version="0.1.0")


def _parse_cors_origins(raw: Optional[str]) -> List[str]:
    if not raw:
        return ["*"]
    raw = raw.strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


CORS_ORIGINS = _parse_cors_origins(os.getenv("CORS_ORIGINS", "*"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Where we persist finished run artifacts (Render free tier: best-effort / may be ephemeral)
RUNS_DIR = Path(os.getenv("RUNS_DIR", "/tmp/pq_runs")).resolve()
RUNS_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Helpers
# -----------------------------
def _tail(s: str, max_chars: int = 2000) -> str:
    if not s:
        return ""
    return s[-max_chars:]


def _safe_read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read results.json: {e}")


def _build_api_artifacts(run_id: str, results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add UI-friendly, deployment-agnostic (relative) URLs for artifacts.

    IMPORTANT:
    - We do NOT modify/reshape engine output.
    - We only ADD a convenience block in the API response.
    """
    base = f"/api/runs/{run_id}"
    api_artifacts: Dict[str, Any] = {
        "results_url": f"{base}/results",
        "report_html_url": None,
        "plots": [],
        "raw": [],
    }

    artifacts = results.get("artifacts") or {}
    # report html
    report_html_path = artifacts.get("report_html")
    if isinstance(report_html_path, str) and report_html_path:
        api_artifacts["report_html_url"] = f"{base}/files/{Path(report_html_path).name}"

    # plots
    plots = artifacts.get("plots") or []
    if isinstance(plots, list):
        for p in plots:
            if not isinstance(p, dict):
                continue
            name = p.get("name")
            path = p.get("path")
            if isinstance(path, str) and path:
                api_artifacts["plots"].append(
                    {"name": name, "url": f"{base}/files/{Path(path).name}"}
                )

    # raw files (e.g., results_json)
    raw = artifacts.get("raw") or []
    if isinstance(raw, list):
        for r in raw:
            if not isinstance(r, dict):
                continue
            name = r.get("name")
            path = r.get("path")
            if isinstance(path, str) and path:
                api_artifacts["raw"].append({"name": name, "url": f"{base}/files/{Path(path).name}"})

    return api_artifacts


def _run_engine(config_bytes: bytes, config_filename: str) -> Dict[str, Any]:
    """
    Runs the frozen pq-engine CLI in an isolated temp workdir, then persists outputs under RUNS_DIR/<run_id>/.
    Returns: (run_id, results_json_dict)
    """
    run_id = str(uuid.uuid4())
    run_dir = (RUNS_DIR / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    # Work directory for engine execution
    with tempfile.TemporaryDirectory(prefix="pq_run_") as tmp:
        tmp_path = Path(tmp).resolve()
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded config
        # Keep extension if provided; engine expects YAML.
        suffix = Path(config_filename).suffix or ".yaml"
        config_path = tmp_path / f"config{suffix}"
        config_path.write_bytes(config_bytes)

        cmd = [
            sys.executable,
            "-m",
            "pq_engine.cli",
            "--config",
            str(config_path),
            "--out",
            str(outputs_dir),
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Engine execution failed.",
                    "returncode": proc.returncode,
                    "stdout_tail": _tail(proc.stdout, 2000),
                    "stderr_tail": _tail(proc.stderr, 4000),
                },
            )

        results_path = outputs_dir / "results.json"
        if not results_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Engine completed but results.json was not produced.",
            )

        # Persist all artifacts (results.json, report.html, pngs, etc.)
        for p in outputs_dir.iterdir():
            if p.is_file():
                shutil.copy2(p, run_dir / p.name)

        results = _safe_read_json(run_dir / "results.json")
        return {"run_id": run_id, "results": results}


# -----------------------------
# Routes
# -----------------------------
@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "service": "pq-app-backend"}


@app.post("/api/analyze")
async def analyze(config: UploadFile = File(...)) -> Response:
    """
    Accepts a YAML config file as multipart/form-data and returns results.json (engine output) as-is,
    with an added convenience block "api_artifacts" containing relative URLs.
    """
    try:
        config_bytes = await config.read()
        payload = _run_engine(config_bytes=config_bytes, config_filename=config.filename or "config.yaml")
        run_id = payload["run_id"]
        results = payload["results"]

        # Add UI-friendly relative URLs without altering engine output
        api_artifacts = _build_api_artifacts(run_id, results)
        merged = dict(results)
        merged["api_artifacts"] = api_artifacts

        return JSONResponse(content=merged, headers={"X-Run-Id": run_id})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {e}")


@app.get("/api/runs/{run_id}/results")
def get_results(run_id: str) -> Dict[str, Any]:
    run_dir = (RUNS_DIR / run_id).resolve()
    results_path = run_dir / "results.json"
    if not results_path.exists():
        raise HTTPException(status_code=404, detail="Run results not found.")
    results = _safe_read_json(results_path)

    # Also include api_artifacts here for convenience
    results_with_links = dict(results)
    results_with_links["api_artifacts"] = _build_api_artifacts(run_id, results)
    return results_with_links


@app.get("/api/runs/{run_id}/files/{filename}")
def get_file(run_id: str, filename: str):
    run_dir = (RUNS_DIR / run_id).resolve()
    file_path = (run_dir / filename).resolve()

    # Prevent path traversal
    if not str(file_path).startswith(str(run_dir) + os.sep):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    # Force download (nice for consultants)
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=None,
    )
