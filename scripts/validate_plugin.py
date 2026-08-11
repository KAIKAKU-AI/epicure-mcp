#!/usr/bin/env python3
"""Validate Cursor Marketplace plugin scaffolding for epicure-mcp.

Checks the submission checklist locally before publishing. Does not talk to
Cursor's review API.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")


def fail(msg: str) -> None:
    print(f"FAIL  {msg}")


def ok(msg: str) -> None:
    print(f"OK    {msg}")


def load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"{path.relative_to(ROOT)}: {exc}")
        return None


def check_frontmatter(path: Path, required: set[str]) -> bool:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        fail(f"{path.relative_to(ROOT)}: missing YAML frontmatter")
        return False
    end = text.find("\n---", 3)
    if end < 0:
        fail(f"{path.relative_to(ROOT)}: unclosed frontmatter")
        return False
    block = text[3:end]
    keys = {
        line.split(":", 1)[0].strip()
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith("#") and ":" in line
    }
    missing = required - keys
    if missing:
        fail(f"{path.relative_to(ROOT)}: missing frontmatter keys {sorted(missing)}")
        return False
    ok(f"{path.relative_to(ROOT)} frontmatter")
    return True


def main() -> int:
    errors = 0

    manifest_path = ROOT / ".cursor-plugin" / "plugin.json"
    if not manifest_path.is_file():
        fail("missing .cursor-plugin/plugin.json")
        return 1

    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        return 1

    name = manifest.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        fail(f"plugin name must be lowercase kebab-case; got {name!r}")
        errors += 1
    else:
        ok(f"plugin name={name}")

    for field in ("description", "version", "license"):
        if not manifest.get(field):
            fail(f"manifest missing recommended field: {field}")
            errors += 1
        else:
            ok(f"manifest.{field}")

    author = manifest.get("author")
    if not isinstance(author, dict) or not author.get("name"):
        fail("manifest.author.name is required for marketplace quality")
        errors += 1
    else:
        ok(f"manifest.author={author['name']}")

    logo = manifest.get("logo")
    if isinstance(logo, str):
        if logo.startswith("/") or ".." in Path(logo).parts:
            fail(f"logo path must be relative without ..: {logo}")
            errors += 1
        elif not (ROOT / logo).is_file():
            fail(f"logo file missing: {logo}")
            errors += 1
        else:
            ok(f"logo={logo}")
    else:
        fail("manifest.logo missing (recommended for marketplace)")
        errors += 1

    mcp_path = ROOT / "mcp.json"
    mcp = load_json(mcp_path) if mcp_path.is_file() else None
    if not isinstance(mcp, dict) or "mcpServers" not in mcp:
        fail("mcp.json must contain mcpServers")
        errors += 1
    else:
        servers = mcp["mcpServers"]
        if not isinstance(servers, dict) or not servers:
            fail("mcpServers must be a non-empty object")
            errors += 1
        else:
            for server_name, cfg in servers.items():
                if not isinstance(cfg, dict):
                    fail(f"mcpServers.{server_name} must be an object")
                    errors += 1
                    continue
                if "url" not in cfg and "command" not in cfg:
                    fail(f"mcpServers.{server_name} needs url or command")
                    errors += 1
                else:
                    ok(f"mcpServers.{server_name}")
                for value in json.dumps(cfg).split("${")[1:]:
                    var = value.split("}", 1)[0]
                    variables = manifest.get("variables")
                    props = variables.get("properties", {}) if isinstance(variables, dict) else {}
                    if var and var not in props:
                        fail(f"${{{var}}} used in mcp.json but not declared in variables")
                        errors += 1

    marketplace = ROOT / ".cursor-plugin" / "marketplace.json"
    if marketplace.is_file():
        # Single-plugin repos should not ship a marketplace manifest.
        fail("remove .cursor-plugin/marketplace.json for this single-plugin repo")
        errors += 1
    else:
        ok("single-plugin layout (no marketplace.json)")

    for skill in (ROOT / "skills").glob("*/SKILL.md"):
        if not check_frontmatter(skill, {"name", "description"}):
            errors += 1

    for rule in (ROOT / "rules").glob("*.mdc"):
        if not check_frontmatter(rule, {"description"}):
            errors += 1

    for agent in (ROOT / "agents").glob("*.md"):
        if not check_frontmatter(agent, {"name", "description"}):
            errors += 1

    for command in (ROOT / "commands").glob("*.md"):
        if not check_frontmatter(command, {"name", "description"}):
            errors += 1

    for required_doc in (
        "README.md",
        "LICENSE",
        "PRIVACY.md",
        "SECURITY.md",
        "SUPPORT.md",
        "TERMS.md",
        "docs/CURSOR_MARKETPLACE_SUBMISSION.md",
    ):
        if (ROOT / required_doc).is_file():
            ok(required_doc)
        else:
            fail(f"missing {required_doc}")
            errors += 1

    # Cursor origin allowlist readiness (defaults in source).
    config_text = (ROOT / "src/epicure_mcp/config.py").read_text(encoding="utf-8")
    if "https://cursor.com" in config_text:
        ok("MCP_ALLOWED_ORIGINS defaults include cursor.com")
    else:
        fail("add https://cursor.com to default MCP_ALLOWED_ORIGINS in config.py")
        errors += 1

    if errors:
        print(f"\n{errors} issue(s). Fix before submitting.")
        return 1
    print("\nPlugin validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
