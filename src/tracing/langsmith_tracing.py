# src/tracing/langsmith_tracing.py
import json
import tempfile
import os
from contextlib import contextmanager
from typing import Optional, Dict, Any

# Best-effort import of the LangSmith client. If the SDK is missing or incompatible,
# we still provide a safe fallback that writes artifacts locally and prints instructions.
try:
    from langsmith import Client
except Exception:
    Client = None  # type: ignore

# Helper to create a client or raise a clear error
def get_client():
    if Client is None:
        raise RuntimeError("langsmith SDK not available in this environment")
    return Client()

@contextmanager
def trace_run(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Create a LangSmith run if possible. Yields a run-like object.
    If run creation fails or returns None, yields a NoopRun that records nothing.
    """
    client = None
    run = None
    try:
        client = get_client()
    except Exception:
        client = None

    if client is None:
        # No SDK available: yield a NoopRun
        class NoopRun:
            id = "noop"
            url = "about:blank"
            def start_span(self, *a, **k): return _NoopSpan()
            def add_artifact(self, *a, **k): pass
            def add_artifact_from_path(self, *a, **k): pass
            def finish(self): pass
        try:
            yield NoopRun()
        finally:
            return

    # Create run with required args for modern SDKs
    try:
        # create_run signature varies; pass inputs and run_type which many versions require
        run = client.create_run(name, inputs=metadata or {}, run_type="tool")
    except TypeError:
        # older/newer SDKs may expect positional args
        try:
            run = client.create_run(name, metadata or {}, "tool")
        except Exception:
            run = None
    except Exception:
        run = None

    # If run is None or missing id/url, provide a safe NoopRun wrapper that still exposes id/url
    if not run or getattr(run, "id", None) is None:
        class PartialRun:
            def __init__(self):
                self.id = None
                self.url = None
            def start_span(self, *a, **k): return _NoopSpan()
            def add_artifact(self, *a, **k): pass
            def add_artifact_from_path(self, *a, **k): pass
            def finish(self): pass
        try:
            yield PartialRun()
        finally:
            return

    # Normal path: yield the real run object
    try:
        yield run
    finally:
        # best-effort finish; some SDKs require finish to make run visible
        try:
            if getattr(run, "finish", None):
                run.finish()
        except Exception:
            pass

class _NoopSpan:
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def finish(self, status="succeeded", error=None): pass
    def add_event(self, *a, **k): pass

def run_url(run) -> str:
    """
    Return a best-effort URL for the run. If the SDK provides run.url, return it.
    If not, return a helpful string with run id or about:blank.
    """
    try:
        if run is None:
            return "about:blank"
        url = getattr(run, "url", None)
        if url:
            return url
        rid = getattr(run, "id", None)
        if rid:
            # best-effort construction; may not be valid for all deployments
            return f"https://api.langsmith.com/runs/{rid}"
    except Exception:
        pass
    return "about:blank"

def attach_json_artifact(run, obj: dict, filename: str = "audit_report.json"):
    """
    Try multiple artifact upload methods depending on SDK version.
    If all fail, write the JSON to a local temp file and return its path.
    Returns:
      - dict with keys {"method": "...", "info": "..."} on success
      - dict with keys {"method": "local_fallback", "path": "<path>"} on fallback
    """
    data = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")

    # If run is falsy, write local file
    if not run or getattr(run, "id", None) is None:
        tmp = _write_local_artifact(data, filename)
        return {"method": "local_fallback", "path": tmp}

    # Try common patterns in order
    # 1) run.add_artifact(Artifact) where Artifact class may be in SDK
    try:
        from langsmith import Artifact  # type: ignore
        art = Artifact.from_bytes(data, filename, mime_type="application/json")
        if getattr(run, "add_artifact", None):
            run.add_artifact(art)
            return {"method": "add_artifact_with_Artifact", "info": filename}
    except Exception:
        pass

    # 2) run.add_artifact_bytes or run.add_bytes
    for method_name in ("add_artifact_bytes", "add_bytes", "add_artifact"):
        fn = getattr(run, method_name, None)
        if callable(fn):
            try:
                # try plausible signatures
                try:
                    fn(data, filename)
                except TypeError:
                    fn({"name": filename, "data": data})
                return {"method": method_name, "info": filename}
            except Exception:
                continue

    # 3) run.add_artifact_from_path or run.add_file or run.upload_file
    tmp_path = None
    try:
        tmp_path = _write_local_artifact(data, filename)
        for method_name in ("add_artifact_from_path", "add_file", "upload_file", "add_artifact_path"):
            fn = getattr(run, method_name, None)
            if callable(fn):
                try:
                    fn(tmp_path)
                    return {"method": method_name, "info": tmp_path}
                except Exception:
                    continue
    except Exception:
        tmp_path = None

    # 4) If nothing worked, return local fallback path
    if tmp_path:
        return {"method": "local_fallback", "path": tmp_path}
    else:
        # final fallback: write to current directory
        fallback = os.path.join(os.getcwd(), filename)
        with open(fallback, "wb") as fh:
            fh.write(data)
        return {"method": "local_fallback", "path": fallback}

def _write_local_artifact(data: bytes, filename: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1] or ".json")
    tmp.write(data)
    tmp.close()
    return tmp.name
