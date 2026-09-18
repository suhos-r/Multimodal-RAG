"""Seed the global KB from ./seed_kb (or --dir). Idempotent-ish: uploads every
file as scope=global, waits for ready, writes seed_manifest.json.

Run:  python scripts/seed_kb.py [--dir seed_kb] [--email seed@local] [--api http://localhost:8000]
Needs: API running (uvicorn or compose), Postgres reachable.
"""
import argparse
import json
import mimetypes
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent


def call(api: str, method: str, path: str, body=None, token: str | None = None, timeout: int = 60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(api + path, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def upload(api: str, token: str, path: Path) -> str:
    import uuid
    boundary = uuid.uuid4().hex
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    blob = path.read_bytes()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"scope\"\r\n\r\nglobal\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n").encode() + blob + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(api + "/api/documents/upload", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                                          "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["doc_id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="seed_kb")
    ap.add_argument("--email", default="seed@example.com")
    ap.add_argument("--password", default="seedpassword1")
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()

    try:
        tok = call(args.api, "POST", "/api/auth/signup",
                   {"email": args.email, "password": args.password})
    except Exception:
        tok = call(args.api, "POST", "/api/auth/login",
                   {"email": args.email, "password": args.password})
    token = tok["access_token"]

    manifest = {}
    files = sorted((ROOT / args.dir).glob("*"))
    if not files:
        print(f"no files in {args.dir}")
        return 1
    for path in files:
        if not path.is_file():
            continue
        doc_id = upload(args.api, token, path)
        call(args.api, "POST", f"/api/documents/{doc_id}/process", {}, token, timeout=300)
        for _ in range(60):
            st = call(args.api, "GET", f"/api/documents/{doc_id}/status", None, token)
            if st["status"] in ("ready", "failed"):
                break
            time.sleep(2)
        print(f"{path.name}: {st['status']}")
        if st["status"] != "ready":
            print("  error:", (st.get("error") or "")[:200])
            return 1
        manifest[path.name] = doc_id
    (ROOT / "seed_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"seeded {len(manifest)} docs -> seed_manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
