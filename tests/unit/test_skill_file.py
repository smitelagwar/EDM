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


def test_acceptance_package_and_app_notes() -> None:
    runner_path = REPO_ROOT / "scripts" / "run-live-acceptance.ps1"
    assert runner_path.is_file()
    runner_text = runner_path.read_text(encoding="utf-8")
    assert "exit 3" in runner_text
    assert "-m live" in runner_text

    template_path = REPO_ROOT / "docs" / "acceptance" / "TEMPLATE.md"
    assert template_path.is_file()
    tpl_text = template_path.read_text(encoding="utf-8")
    assert "L1" in tpl_text and "L12" in tpl_text
    assert "M1" in tpl_text and "M8" in tpl_text

    for note_name in ("autocad.md", "winrar.md", "chrome.md", "g-menu.md"):
        note_path = REPO_ROOT / "docs" / "app-notes" / note_name
        assert note_path.is_file()
        note_text = note_path.read_text(encoding="utf-8")
        assert "Önerilen Yöntem" in note_text
        assert "Bilinen Tuzak" in note_text
        assert "Doğrulama Durumu" in note_text

    skill_text = (REPO_ROOT / "integrations" / "skills" / "edm-desktop" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "docs/app-notes/g-menu.md" in skill_text
    assert "docs/app-notes/gmenu.md" not in skill_text


def test_readme_changelog_and_security_docs() -> None:
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_tr = (REPO_ROOT / "README.tr.md").read_text(encoding="utf-8")
    changelog = REPO_ROOT / "CHANGELOG.md"
    security = REPO_ROOT / "SECURITY.md"
    assert changelog.is_file()
    assert security.is_file()

    for text in (readme_en, readme_tr):
        assert "uv tool install" in text
        assert "docs/integrations/antigravity.md" in text
        assert "LOCALAPPDATA" in text
        assert "MIT" in text
        assert "draw_path" in text
        assert "request_user_region" in text

    assert "0.1.0" in changelog.read_text(encoding="utf-8")
    sec_text = security.read_text(encoding="utf-8")
    assert "Local\\EDM_ABORT" in sec_text
    assert "127.0.0.1" in sec_text
