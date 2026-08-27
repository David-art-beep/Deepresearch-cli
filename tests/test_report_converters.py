from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

from deepresearch_cli.converters import md_docx, md_pdf
from deepresearch_cli.converters._markdown import strip_static_toc
from deepresearch_cli.node_validators import docx, pdf


def _write_context(path: Path, source: Path, destination: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "inputs": {"report": [{"path": str(source)}]},
                "outputs": {"document": {"path": str(destination)}},
            }
        ),
        encoding="utf-8",
    )


def _write_docx(path: Path, text: str = "Report") -> None:
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", document)


def _write_pdf(path: Path) -> None:
    path.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\nstartxref\n0\n%%EOF\n"
    )


def test_strip_static_toc_keeps_report_content_and_code_fences():
    markdown = """# Report

## 目录

- [第一章](#第一章)
  - [细节](#细节)

## 第一章

正文。

```markdown
## 目录
- [示例](#示例)
```

## 参考文献

[1] Source
"""

    cleaned = strip_static_toc(markdown)

    assert cleaned.startswith("# Report\n\n## 第一章")
    assert "- [第一章](#第一章)" not in cleaned
    assert "```markdown\n## 目录\n- [示例](#示例)\n```" in cleaned
    assert "## 参考文献\n\n[1] Source" in cleaned


def test_markdown_docx_node_uses_context_and_pandoc(monkeypatch, tmp_path):
    source = tmp_path / "report.md"
    source.write_text(
        "# Report\n\n## 目录\n\n- [正文](#正文)\n\n## 正文\n\nContent\n",
        encoding="utf-8",
    )
    destination = tmp_path / "report.docx"
    context = tmp_path / "context.json"
    _write_context(context, source, destination)
    resources = tmp_path / "resources"
    resources.mkdir()
    reference = resources / "reference.docx"
    _write_docx(reference, "Template")
    monkeypatch.setenv("DEEPRESEARCH_NODE_CONTEXT", str(context))
    monkeypatch.setattr(md_docx.shutil, "which", lambda name: "/test/pandoc")

    def fake_run(command, **kwargs):
        assert command[0] == "/test/pandoc"
        assert "--from=gfm" in command
        assert "--standalone" in command
        assert "--shift-heading-level-by=-1" in command
        assert "--toc" in command
        assert command[command.index("--reference-doc") + 1] == str(reference)
        prepared_source = Path(command[1])
        assert prepared_source != source
        prepared_text = prepared_source.read_text(encoding="utf-8")
        assert "## 目录" not in prepared_text
        assert "## 正文" in prepared_text
        output = Path(command[command.index("--output") + 1])
        _write_docx(output)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(md_docx.subprocess, "run", fake_run)

    assert md_docx.main() == 0
    assert destination.is_file()


def test_markdown_docx_reports_missing_pandoc(monkeypatch, tmp_path, capsys):
    source = tmp_path / "report.md"
    source.write_text("# Report\n", encoding="utf-8")
    context = tmp_path / "context.json"
    _write_context(context, source, tmp_path / "report.docx")
    monkeypatch.setenv("DEEPRESEARCH_NODE_CONTEXT", str(context))
    monkeypatch.delenv("DEEPRESEARCH_PANDOC", raising=False)
    monkeypatch.setattr(md_docx.shutil, "which", lambda name: None)

    assert md_docx.main() == 2
    assert "Pandoc is required" in capsys.readouterr().err


def test_markdown_pdf_node_uses_context_pandoc_typst_and_template(
    monkeypatch, tmp_path
):
    source = tmp_path / "report.md"
    source.write_text(
        "# Report\n\n## 目录\n\n- [正文](#正文)\n\n## 正文\n\nContent\n",
        encoding="utf-8",
    )
    destination = tmp_path / "report.pdf"
    context = tmp_path / "context.json"
    _write_context(context, source, destination)
    resources = tmp_path / "resources"
    resources.mkdir()
    template = resources / "report.typ"
    template.write_text("$body$\n", encoding="utf-8")
    monkeypatch.setenv("DEEPRESEARCH_NODE_CONTEXT", str(context))
    monkeypatch.setattr(md_pdf.shutil, "which", lambda name: f"/test/{name}")

    def fake_run(command, **kwargs):
        assert command[0] == "/test/pandoc"
        assert "--from=gfm" in command
        assert "--to=typst" in command
        assert "--standalone" in command
        assert "--shift-heading-level-by=-1" in command
        assert "--toc" in command
        assert "--pdf-engine=/test/typst" in command
        assert command[command.index("--template") + 1] == str(template)
        prepared_source = Path(command[1])
        assert prepared_source != source
        prepared_text = prepared_source.read_text(encoding="utf-8")
        assert "## 目录" not in prepared_text
        assert "## 正文" in prepared_text
        output = Path(command[command.index("--output") + 1])
        _write_pdf(output)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(md_pdf.subprocess, "run", fake_run)

    assert md_pdf.main() == 0
    assert destination.is_file()


def test_docx_validator_accepts_ooxml_and_rejects_plain_text(monkeypatch, tmp_path):
    source = tmp_path / "unused.md"
    source.write_text("unused", encoding="utf-8")
    destination = tmp_path / "report.docx"
    context = tmp_path / "context.json"
    _write_context(context, source, destination)
    monkeypatch.setenv("DEEPRESEARCH_NODE_CONTEXT", str(context))

    _write_docx(destination)
    assert docx.main() == 0

    destination.write_text("not a docx", encoding="utf-8")
    assert docx.main() == 1


def test_pdf_validator_accepts_pdf_and_rejects_plain_text(monkeypatch, tmp_path):
    source = tmp_path / "unused.html"
    source.write_text("unused", encoding="utf-8")
    destination = tmp_path / "report.pdf"
    context = tmp_path / "context.json"
    _write_context(context, source, destination)
    monkeypatch.setenv("DEEPRESEARCH_NODE_CONTEXT", str(context))

    _write_pdf(destination)
    assert pdf.main() == 0

    destination.write_text("not a pdf", encoding="utf-8")
    assert pdf.main() == 1
