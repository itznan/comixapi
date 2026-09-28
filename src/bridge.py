"""
Node.js security VM bridge for request signing and payload decryption.
"""

import json
import subprocess
from pathlib import Path


class NodeSignerBridge:
    """Bridge communicating with comix_signer.js over stdin/stdout."""

    def __init__(self, script_path: str, secure_js_path: str, cfg_token: str, manga_id: str):
        self.script_path = str(Path(script_path).resolve())
        self.secure_js_path = str(Path(secure_js_path).resolve()).replace("\\", "/")
        self.cfg_token = cfg_token
        self.manga_id = manga_id
        self._msg_id = 0

        self.proc = subprocess.Popen(
            ["node", self.script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8"
        )

        res = self._send({
            "action": "init",
            "securePath": self.secure_js_path,
            "cfg": self.cfg_token,
            "mangaId": self.manga_id
        })
        if not res.get("success"):
            raise RuntimeError(f"Signer bridge init failed: {res.get('error')}")

    def _send(self, payload: dict) -> dict:
        self._msg_id += 1
        payload["id"] = self._msg_id
        line = json.dumps(payload) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()
        resp_line = self.proc.stdout.readline()
        if not resp_line:
            err = self.proc.stderr.read()
            raise RuntimeError(f"Signer bridge process exited unexpectedly: {err}")
        return json.loads(resp_line)

    def sign(self, url_path: str, params: dict = None, chapter_id: str = None, manga_id: str = None) -> dict:
        payload = {
            "action": "sign",
            "urlPath": url_path,
            "params": params or {},
            "chapterId": chapter_id
        }
        if manga_id:
            payload["mangaId"] = manga_id
        res = self._send(payload)
        if not res.get("success"):
            raise RuntimeError(f"Failed to sign request {url_path}: {res.get('error')}")
        return res.get("params", {})

    def decrypt(self, url_path: str, data: dict, chapter_id: str = None, manga_id: str = None) -> dict:
        payload = {
            "action": "decrypt",
            "urlPath": url_path,
            "chapterId": chapter_id,
            "data": data
        }
        if manga_id:
            payload["mangaId"] = manga_id
        res = self._send(payload)
        if not res.get("success"):
            raise RuntimeError(f"Failed to decrypt response for {url_path}: {res.get('error')}")
        return res.get("data", {})

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        except Exception:
            pass
