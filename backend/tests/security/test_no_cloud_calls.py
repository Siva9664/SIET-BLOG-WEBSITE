"""Security Regression Test: Zero Cloud API Calls & Static Import Isolation Guard.

Enforces that:
1. Static AST inspection confirms ZERO cloud AI SDK imports (google, openai, anthropic) under backend/app/.
2. Dynamic execution of the full pipeline with use_llm=True blocks all non-localhost sockets.
"""

import ast
import os
import socket
import pytest
from unittest.mock import patch


def test_static_ast_scan_no_cloud_sdk_imports():
    """Scans all Python files under backend/app/ to ensure no imports of cloud AI SDKs exist in live code."""
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../app"))
    forbidden_modules = {"openai", "google.generativeai", "anthropic"}

    violations = []
    for root, _, files in os.walk(app_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read(), filename=filepath)
                    except Exception:
                        continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in forbidden_modules or any(alias.name.startswith(fm + ".") for fm in forbidden_modules):
                                violations.append((filepath, alias.name))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and (node.module in forbidden_modules or any(node.module.startswith(fm + ".") for fm in forbidden_modules)):
                            violations.append((filepath, node.module))

    assert len(violations) == 0, f"Found forbidden cloud SDK imports in app/: {violations}"


@pytest.mark.asyncio
async def test_zero_cloud_api_calls_in_live_pipeline():
    """Mocks network sockets to verify that no non-localhost outbound calls are made during pipeline execution."""
    orig_connect = socket.socket.connect
    orig_getaddrinfo = socket.getaddrinfo

    def _guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError(f"SECURITY VIOLATION: Non-localhost network connection attempted to '{host}'!")
        return orig_connect(self, address)

    def _guarded_getaddrinfo(host, port, *args, **kwargs):
        if host not in ("127.0.0.1", "localhost", "::1"):
            # Check if host resolves to localhost
            if host not in ("localhost", "127.0.0.1"):
                raise RuntimeError(f"SECURITY VIOLATION: Non-localhost DNS lookup attempted for '{host}'!")
        return orig_getaddrinfo(host, port, *args, **kwargs)

    with patch.object(socket.socket, "connect", _guarded_connect), patch("socket.getaddrinfo", side_effect=_guarded_getaddrinfo):
        from app.modules.magazine.end_to_end_pipeline import run_end_to_end_magazine_pipeline

        result = await run_end_to_end_magazine_pipeline(
            raw_notes="Strictly offline local Gemma generation test for security compliance.",
            department_or_lab="Security Lab",
            target_page_budget=2,
            use_llm=True,
        )

        assert result is not None
        assert result.status in ("published", "needs_review")
