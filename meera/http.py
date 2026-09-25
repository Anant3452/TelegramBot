"""Tiny JSON-over-HTTP helper on top of urllib, so the project has no dependencies."""

import json
import os
import ssl
import urllib.error
import urllib.request


_SSL = ssl.create_default_context()
# python.org builds on macOS ship without CA certs; the system bundle fixes local runs.
if os.path.exists("/etc/ssl/cert.pem"):
    _SSL.load_verify_locations("/etc/ssl/cert.pem")


class HTTPError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:500]}")
        self.status = status
        self.body = body


def request(method, url, *, headers=None, body=None, timeout=60, raw=False):
    data = None
    headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode()
        headers.setdefault("Content-Type", "application/json")
    headers.setdefault("User-Agent", "meera-content-bot/1.0")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as e:
        raise HTTPError(e.code, e.read().decode(errors="replace")) from None
    if raw:
        return payload
    return json.loads(payload) if payload else None
