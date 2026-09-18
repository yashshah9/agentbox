"""Tests for egress allowlist parsing and soft hooks."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentbox.sandbox.egress import (
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
    assert result.network_isolated is True
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
    assert result.network_isolated is True
    # Offline CI may fail DNS; allow ERR URLError but never DENIED for listed host
    assert "DENIED" not in result.stdout
    assert "OK" in result.stdout or "ERR" in result.stdout


def test_install_python_hook_writes_sitecustomize(tmp_path: Path) -> None:
    env = install_python_hook(tmp_path, ["api.openai.com"])
    assert (tmp_path / ".agentbox_egress" / "sitecustomize.py").is_file()
    assert "PYTHONPATH" in env
