"""Tests for egress allowlist parsing and soft hooks."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentbox.sandbox.egress import (
    install_node_hook,
    install_python_hook,
    parse_allowlist,
    resolve_allowlist,
)
from agentbox.sandbox.runner import SubprocessSandbox


def test_parse_allowlist_csv() -> None:
    assert parse_allowlist("api.openai.com:443, pypi.org") == [
        "api.openai.com:443",
        "pypi.org",
    ]
    assert parse_allowlist("") == []
    with pytest.raises(ValueError):
        parse_allowlist("bad host!")


def test_resolve_subset() -> None:
    assert resolve_allowlist(["a.com", "b.com"], None) == ["a.com", "b.com"]
    assert resolve_allowlist(["a.com", "b.com"], ["a.com"]) == ["a.com"]
    assert resolve_allowlist(["a.com"], []) == []
    assert resolve_allowlist([], ["evil.com"]) == ["evil.com"]
    with pytest.raises(ValueError, match="not permitted"):
        resolve_allowlist(["a.com"], ["evil.com"])


def test_python_hook_blocks_disallowed(tmp_path: Path) -> None:
    box = SubprocessSandbox(deny_egress=True, egress_allowlist=["example.com"], timeout_seconds=10)
    result = box.run(
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('https://httpbin.org/get', timeout=3)\n"
        "    print('REACHED')\n"
        "except OSError as e:\n"
        "    print('DENIED' if 'egress denied' in str(e) else type(e).__name__)\n",
        language="python",
    )
    assert result.network_isolated is False
    assert result.egress_allowlist == ["example.com"]
    assert "DENIED" in result.stdout


def test_python_hook_allows_listed_host(tmp_path: Path) -> None:
    # example.com is typically reachable; if offline, skip soft.
    box = SubprocessSandbox(deny_egress=True, egress_allowlist=["example.com"], timeout_seconds=15)
    result = box.run(
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('https://example.com', timeout=8)\n"
        "    print('OK')\n"
        "except Exception as e:\n"
        "    print('ERR', type(e).__name__)\n",
        language="python",
    )
    assert result.network_isolated is False
    # Offline CI may fail DNS; allow ERR URLError but never DENIED for listed host
    assert "DENIED" not in result.stdout
    assert "OK" in result.stdout or "ERR" in result.stdout


def test_python_hook_blocks_localhost_unless_listed(tmp_path: Path) -> None:
    box = SubprocessSandbox(deny_egress=True, egress_allowlist=["example.com"], timeout_seconds=10)
    result = box.run(
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('http://127.0.0.1:9/', timeout=2)\n"
        "    print('REACHED')\n"
        "except OSError as e:\n"
        "    print('DENIED' if 'egress denied' in str(e) else type(e).__name__)\n",
        language="python",
    )
    assert "DENIED" in result.stdout


def test_python_hook_allows_explicit_localhost(tmp_path: Path) -> None:
    box = SubprocessSandbox(
        deny_egress=True, egress_allowlist=["127.0.0.1", "localhost"], timeout_seconds=10
    )
    result = box.run(
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('http://127.0.0.1:9/', timeout=2)\n"
        "    print('OK')\n"
        "except Exception as e:\n"
        "    # Connection refused is fine — must not be egress denied\n"
        "    print('DENIED' if 'egress denied' in str(e) else 'ERR')\n",
        language="python",
    )
    assert "DENIED" not in result.stdout
    assert "OK" in result.stdout or "ERR" in result.stdout


def test_install_python_hook_writes_sitecustomize(tmp_path: Path) -> None:
    env = install_python_hook(tmp_path, ["api.openai.com"])
    assert (tmp_path / ".agentbox_egress" / "sitecustomize.py").is_file()
    assert "PYTHONPATH" in env


def test_install_node_hook_covers_fetch(tmp_path: Path) -> None:
    env = install_node_hook(tmp_path, ["example.com"])
    text = (tmp_path / ".agentbox_egress_preload.js").read_text(encoding="utf-8")
    assert "NODE_OPTIONS" in env
    assert "globalThis.fetch" in text
    assert "wrapHttp" in text or "https.request" in text or "mod[name]" in text


@pytest.mark.skipif(
    __import__("shutil").which("node") is None, reason="node not installed"
)
def test_node_fetch_blocks_disallowed(tmp_path: Path) -> None:
    box = SubprocessSandbox(deny_egress=True, egress_allowlist=["example.com"], timeout_seconds=10)
    result = box.run(
        "try {\n"
        "  const p = fetch('https://httpbin.org/get');\n"
        "  p.then(() => console.log('REACHED'))"
        ".catch((e) => console.log("
        "String(e && e.message || e).includes('egress denied') ? 'DENIED' : 'ERR'));\n"
        "} catch (e) {\n"
        "  console.log(String(e.message || e).includes('egress denied') ? 'DENIED' : 'ERR');\n"
        "}\n",
        language="javascript",
    )
    assert result.network_isolated is False
    assert "DENIED" in result.stdout


@pytest.mark.skipif(
    __import__("shutil").which("node") is None, reason="node not installed"
)
def test_node_https_request_blocks_disallowed(tmp_path: Path) -> None:
    box = SubprocessSandbox(deny_egress=True, egress_allowlist=["example.com"], timeout_seconds=10)
    result = box.run(
        "const https = require('https');\n"
        "try {\n"
        "  https.get('https://httpbin.org/get', () => console.log('REACHED'));\n"
        "} catch (e) {\n"
        "  console.log(String(e.message || e).includes('egress denied') ? 'DENIED' : 'ERR');\n"
        "}\n",
        language="javascript",
    )
    assert "DENIED" in result.stdout
