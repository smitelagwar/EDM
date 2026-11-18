from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_skill_frontmatter() -> None:
    skill_path = REPO_ROOT / "integrations" / "skills" / "edm-desktop" / "SKILL.md"
    assert skill_path.is_file()
    raw = skill_path.read_text(encoding="utf-8")
    assert raw.startswith("---\n")
    parts = raw.split("---\n", 2)
    assert len(parts) == 3
    frontmatter, body = parts[1], parts[2]
    assert "name: edm-desktop" in frontmatter
    assert "description:" in frontmatter
    body_lines = body.strip().splitlines()
    assert 1 <= len(body_lines) <= 150
    assert "doctor" in body
    assert "ISOLATED_DESKTOP" in body


def test_install_script_has_no_default_writes() -> None:
    script_path = REPO_ROOT / "scripts" / "install.ps1"
    assert script_path.is_file()
    text = script_path.read_text(encoding="utf-8")
    assert "param(" in text
    assert "$WriteConfig" in text

    # Ensure Set-Content / Out-File appear ONLY inside the if ($WriteConfig) block.
    before_guard, sep, after_guard = text.partition("if ($WriteConfig)")
    assert sep == "if ($WriteConfig)"
    assert "Set-Content" not in before_guard
    assert "Out-File" not in before_guard
    assert ".bak-" in after_guard

    for doc_name in ("antigravity.md", "codex.md", "claude-code.md", "gemini-cli.md"):
        doc_path = REPO_ROOT / "docs" / "integrations" / doc_name
        assert doc_path.is_file()
        assert "edm" in doc_path.read_text(encoding="utf-8")
