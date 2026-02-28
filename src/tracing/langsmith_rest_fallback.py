# src/tracing/langsmith_rest_fallback.py
import os
import json
import tempfile
import requests
from typing import Dict, Any, Optional

LANGSMITH_BASE = os.getenv("LANGSMITH_BASE_URL", "https://api.langsmith.com")
API_KEY = os.getenv("LANGSMITH_API_KEY")

def _write_local_artifact(data: bytes, filename: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="." + filename.split(".")[-1])
    tmp.write(data)
    tmp.close()
    return tmp.name

def create_run_rest(name: str, inputs: Dict[str, Any], run_type: str = "tool") -> Optional[Dict[str, Any]]:
    if not API_KEY:
        raise RuntimeError("LANGSMITH_API_KEY not set in environment")
    url = f"{LANGSMITH_BASE}/v1/runs"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"name": name, "inputs": inputs, "run_type": run_type}
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    if resp.status_code not in (200, 201):
        return None
    return resp.json()

def upload_artifact_rest(run_id: str, filename: str, data: bytes) -> bool:
    if not API_KEY:
        raise RuntimeError("LANGSMITH_API_KEY not set in environment")
    url = f"{LANGSMITH_BASE}/v1/runs/{run_id}/artifacts"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    files = {"file": (filename, data, "application/json")}
    resp = requests.post(url, headers=headers, files=files, timeout=60)
    return resp.status_code in (200, 201)

def finish_run_rest(run_id: str) -> bool:
    if not API_KEY:
        raise RuntimeError("LANGSMITH_API_KEY not set in environment")
    url = f"{LANGSMITH_BASE}/v1/runs/{run_id}/finish"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={}, timeout=10)
    return resp.status_code in (200, 201)

def run_and_upload_report(report_obj: Dict[str, Any], repo_meta: Dict[str, Any] = None) -> Dict[str, Any]:
    data = json.dumps(report_obj, indent=2).encode("utf-8")
    filename = "audit_report.json"
    try:
        inputs = repo_meta or {"repo": "unknown"}
        created = create_run_rest("The-Automaton-Auditor run", inputs=inputs, run_type="tool")
        if not created or "id" not in created:
            path = _write_local_artifact(data, filename)
            return {"status": "local_fallback", "path": path, "error": "create_run returned no id"}
        run_id = created["id"]
        ok = upload_artifact_rest(run_id, filename, data)
        if not ok:
            path = _write_local_artifact(data, filename)
            return {"status": "local_fallback", "path": path, "error": "artifact upload failed"}
        finish_ok = finish_run_rest(run_id)
        run_url = created.get("url") or f"{LANGSMITH_BASE}/runs/{run_id}"
        return {"status": "ok", "run_id": run_id, "run_url": run_url, "finished": finish_ok}
    except Exception as e:
        path = _write_local_artifact(data, filename)
        return {"status": "local_fallback", "path": path, "error": str(e)}
