"""Egress allowlist helpers (userspace soft filter).

ponytail: soft allowlist via Python sitecustomize / Node --require hooks — not a
kernel firewall. Determined code can bypass. Ceiling = iptables/NET_ADMIN custom
runtime image or gVisor network policy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_HOST_RE = re.compile(r"^[A-Za-z0-9._\-]+(?::\d{1,5})?$")


def parse_allowlist(raw: str | list[str] | None) -> list[str]:
    """Parse comma-separated or list allowlist into unique host[:port] entries."""
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",")]
    else:
        parts = [str(p).strip() for p in raw]
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        if not _HOST_RE.match(part):
            raise ValueError(f"Invalid egress allowlist entry: {part!r}")
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def resolve_allowlist(
    global_hosts: list[str],
    request_hosts: list[str] | None,
) -> list[str]:
    """Intersect request with global policy.

    - ``request_hosts is None`` → use global (may be empty = deny-all)
    - global empty → request wins (or empty)
    - both set → request hostnames must be ⊆ global; empty request = deny-all
    """
    global_norm = [h.lower() for h in global_hosts]
    global_keys = {h.split(":")[0] for h in global_norm}
    if request_hosts is None:
        return list(global_norm)
    req = parse_allowlist(request_hosts)
    if not global_keys:
        return req
    if not req:
        return []
    bad = [h for h in req if h.split(":")[0] not in global_keys]
    if bad:
        raise ValueError(
            "egress_allowlist entries not permitted by AGENTBOX_EGRESS_ALLOWLIST: "
            + ", ".join(bad)
        )
    return req


def install_python_hook(workspace: Path, hosts: list[str]) -> dict[str, str]:
    """Write sitecustomize hook; return env vars to enable it."""
    hook_dir = workspace / ".agentbox_egress"
    hook_dir.mkdir(parents=True, exist_ok=True)
    hosts_json = json.dumps(hosts)
    (hook_dir / "sitecustomize.py").write_text(
        f'''# agentbox egress soft allowlist — auto-generated
import socket
import ipaddress

_ALLOWED = {{h.lower() for h in {hosts_json}}}
_ALLOWED_HOSTS = {{h.split(":")[0] for h in _ALLOWED}}
_ALLOWED_IPS: set[str] = set()
for _h in list(_ALLOWED_HOSTS):
    try:
        _ALLOWED_IPS.add(str(ipaddress.ip_address(_h)))
    except ValueError:
        pass

_orig_getaddrinfo = socket.getaddrinfo
_orig_connect = socket.socket.connect


def _host_ok(host: str) -> bool:
    h = (host or "").lower().strip("[]")
    if not h or h in {{"localhost", "127.0.0.1", "::1"}}:
        return True
    if h in _ALLOWED_HOSTS or h in _ALLOWED_IPS:
        return True
    try:
        ipaddress.ip_address(h)
        return h in _ALLOWED_IPS
    except ValueError:
        return h in _ALLOWED_HOSTS


def getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
    if not _host_ok(str(host)):
        raise OSError(f"agentbox egress denied: {{host}}")
    results = _orig_getaddrinfo(host, *args, **kwargs)
    for item in results:
        try:
            sockaddr = item[4]
            if sockaddr:
                _ALLOWED_IPS.add(str(sockaddr[0]))
        except (IndexError, TypeError, ValueError):
            pass
    return results


def _connect(self, address):  # type: ignore[no-untyped-def]
    host = address[0] if isinstance(address, tuple) and address else address
    if isinstance(host, bytes):
        host = host.decode("utf-8", "replace")
    if not _host_ok(str(host)):
        raise OSError(f"agentbox egress denied: {{host}}")
    return _orig_connect(self, address)


socket.getaddrinfo = getaddrinfo
socket.socket.connect = _connect
''',
        encoding="utf-8",
    )
    return {"PYTHONPATH": str(hook_dir.resolve())}


def install_node_hook(workspace: Path, hosts: list[str]) -> dict[str, str]:
    """Write Node --require preload; return env vars to enable it."""
    path = workspace / ".agentbox_egress_preload.js"
    hosts_json = json.dumps(hosts)
    path.write_text(
        f"""/* agentbox egress soft allowlist — auto-generated */
const net = require('net');
const allowed = new Set({hosts_json}.map((h) => String(h).toLowerCase()));
const allowedHosts = new Set([...allowed].map((h) => h.split(':')[0]));
function hostOk(host) {{
  if (!host) return true;
  const h = String(host).toLowerCase().replace(/^\\[|\\]$/g, '');
  if (h === 'localhost' || h === '127.0.0.1' || h === '::1') return true;
  return allowedHosts.has(h) || allowed.has(h);
}}
const origConnect = net.Socket.prototype.connect;
net.Socket.prototype.connect = function (...args) {{
  let host = null;
  if (typeof args[0] === 'object' && args[0] !== null) {{
    host = args[0].host || args[0].hostname;
  }} else if (typeof args[1] === 'string') {{
    host = args[1];
  }} else if (typeof args[0] === 'string' && args[0].includes(':')) {{
    host = args[0].split(':')[0];
  }}
  if (host && !hostOk(host)) {{
    const err = new Error('agentbox egress denied: ' + host);
    err.code = 'EGRESS_DENIED';
    throw err;
  }}
  return origConnect.apply(this, args);
}};
""",
        encoding="utf-8",
    )
    return {"NODE_OPTIONS": f"--require {path.resolve()}"}
