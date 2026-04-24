#!/usr/bin/env python3
"""
extract_manuscript.py — Parse a .docx manuscript into organized markdown chunks.

Usage:
    python3 extract_manuscript.py --config path/to/config.yaml

Outputs (relative to config.extracted_path):
    front_quote.md           — opening pull quote for the landing page
    manifest.json            — index of all extracted content with word counts
    full_outline.md          — complete chapter + case study TOC
    chapters/                — one .md file per chapter (raw source)
    case-studies/            — one .md file per cliff-note case study (raw source)
    appendix/                — appendix sections (state survey, etc.)

The script is idempotent — safe to rerun.  Output files are overwritten.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterator

try:
    import yaml
    from docx import Document
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph as DocxParagraph
    from docx.table import Table as DocxTable
except ImportError as e:
    sys.exit(
        f"Missing dependency: {e}\n"
        "Install with: pip install python-docx pyyaml"
    )


# ── Heading / style patterns ───────────────────────────────────────────────────
# Chapter headings in the manuscript body use Normal style with this exact text.
CHAPTER_HEADING_RE = re.compile(r"^(?:BONUS\s+)?CHAPTER\s+(\d+)$")

# TOC entries: "Chapter 1   The Strategy in One Sentence   ___"
TOC_ENTRY_RE = re.compile(r"^Chapter\s+(\d+)\s+(.+?)\s*_+\s*$")

# Case study label lines: "CLIFF NOTE CASE STUDY 17"
CS_LABEL_RE = re.compile(r"^CLIFF NOTE CASE STUDY\s+(\d+)$")

# The opening line of the manuscript pull-quote block
QUOTE_START = "Every chapter in this Codex is a door"


# ── Text utilities ─────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def word_count(text: str) -> int:
    return len(text.split())


# ── Run / paragraph → markdown ─────────────────────────────────────────────────

def run_to_md(run) -> str:
    t = run.text
    if not t:
        return ""
    if run.bold and run.italic:
        return f"***{t}***"
    if run.bold:
        return f"**{t}**"
    if run.italic:
        return f"*{t}*"
    return t


def para_to_md(para) -> str:
    """Convert a single paragraph to a markdown string, respecting style."""
    style = para.style.name if para.style else ""
    text = "".join(run_to_md(r) for r in para.runs).strip()
    if not text:
        return ""

    if style == "SecHead":
        return f"## {text}"

    if style == "BulletNum":
        return f"1. {text}"

    if style == "List Paragraph":
        # Check for numPr to distinguish numbered vs bullet
        ppr = para._element.find(qn("w:pPr"))
        if ppr is not None and ppr.find(qn("w:numPr")) is not None:
            return f"1. {text}"
        return f"- {text}"

    return text


def table_to_md(table) -> str:
    rows = []
    for i, row in enumerate(table.rows):
        cells = [c.text.strip().replace("\n", " ") for c in row.cells]
        rows.append("| " + " | ".join(cells) + " |")
        if i == 0:
            rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(rows)


# ── Document block iterator ────────────────────────────────────────────────────

def iter_blocks(doc) -> Iterator[tuple[str, object]]:
    """Yield ('para', para) or ('table', table) in body order."""
    for child in doc.element.body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag == "p":
            yield "para", DocxParagraph(child, doc)
        elif tag == "tbl":
            yield "table", DocxTable(child, doc)


def blocks_to_markdown(blocks: list[tuple[str, object]]) -> str:
    """Render a list of (type, obj) blocks to a single markdown string."""
    parts: list[str] = []
    for btype, obj in blocks:
        if btype == "para":
            md = para_to_md(obj)
            if md:
                parts.append(md)
        elif btype == "table":
            md = table_to_md(obj)
            if md:
                parts.append(md)
    return "\n\n".join(parts)


# ── TOC extraction ─────────────────────────────────────────────────────────────

def extract_toc(blocks: list[tuple]) -> dict[int, str]:
    """Return {chapter_num: title} from TOC paragraph matches."""
    toc: dict[int, str] = {}
    for btype, obj in blocks:
        if btype != "para":
            continue
        m = TOC_ENTRY_RE.match(obj.text.strip())
        if m:
            toc[int(m.group(1))] = m.group(2).strip()
    return toc


# ── Front-page quote extraction ────────────────────────────────────────────────

def extract_front_quote(blocks: list[tuple]) -> str:
    """
    Locate the pull-quote block that starts with QUOTE_START and return it
    formatted as a markdown block-quote with attribution.
    """
    quote_lines: list[str] = []
    attribution = ""
    in_quote = False

    for btype, obj in blocks:
        if btype != "para":
            continue
        text = obj.text.strip()
        if not text:
            continue

        if QUOTE_START in text:
            in_quote = True

        if in_quote:
            if text.startswith("—") or text.startswith("—"):
                attribution = text
                break
            # Stop collecting after we have the 4-line quote
            if len(quote_lines) >= 4 and not text.startswith("Every") and not text.startswith("That"):
                if text.startswith("Read.") or text.startswith("When you"):
                    break
            quote_lines.append(text)

    if not quote_lines:
        return ""

    # Keep the four-line quote only
    core = quote_lines[:4]
    md_lines = [f"> {line}" for line in core]
    if attribution:
        md_lines += [">", f"> {attribution}"]
    return "\n".join(md_lines)


# ── Main extraction ────────────────────────────────────────────────────────────

def extract(config_path: str) -> None:
    cfg_path = Path(config_path).resolve()
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    codex_slug: str = cfg["codex_slug"]
    manuscript_path = (cfg_path.parent / cfg["manuscript_path"]).resolve()
    extracted_path = (cfg_path.parent / cfg["extracted_path"]).resolve()

    print(f"Loading: {manuscript_path}")
    doc = Document(str(manuscript_path))

    # Collect every block exactly once
    all_blocks = list(iter_blocks(doc))
    print(f"Total blocks: {len(all_blocks)}")

    # ── Find document region boundaries ───────────────────────────────────────
    first_chapter_idx: int | None = None   # First "CHAPTER N" Normal para
    first_appendix_idx: int | None = None  # First Heading 2 (appendix start)

    for i, (btype, obj) in enumerate(all_blocks):
        if btype != "para":
            continue
        text = obj.text.strip()
        style = obj.style.name if obj.style else ""

        if first_chapter_idx is None and CHAPTER_HEADING_RE.match(text):
            first_chapter_idx = i

        if first_appendix_idx is None and "Heading 2" in style and text:
            first_appendix_idx = i

    if first_chapter_idx is None:
        sys.exit("ERROR: No 'CHAPTER N' marker found. Check CHAPTER_HEADING_RE pattern.")

    print(f"First chapter block : index {first_chapter_idx}")
    print(f"First appendix block: index {first_appendix_idx}")

    front_matter_blocks = all_blocks[:first_chapter_idx]
    chapter_region = all_blocks[first_chapter_idx:first_appendix_idx]
    appendix_region = all_blocks[first_appendix_idx:] if first_appendix_idx else []

    # ── TOC and front quote ────────────────────────────────────────────────────
    toc = extract_toc(front_matter_blocks)
    front_quote = extract_front_quote(front_matter_blocks)
    print(f"TOC entries found   : {len(toc)}")

    # ── Split chapters ─────────────────────────────────────────────────────────
    chapters: list[dict] = []
    current: dict | None = None

    for btype, obj in chapter_region:
        if btype == "para":
            text = obj.text.strip()
            m = CHAPTER_HEADING_RE.match(text)
            if m:
                if current is not None:
                    chapters.append(current)
                num = int(m.group(1))
                current = {
                    "number": num,
                    "title": toc.get(num, f"Chapter {num}"),
                    "blocks": [],
                }
                continue
        if current is not None:
            current["blocks"].append((btype, obj))

    if current and current["blocks"]:
        chapters.append(current)

    print(f"Chapters extracted  : {len(chapters)}")

    # ── Split case studies ─────────────────────────────────────────────────────
    case_studies: list[dict] = []
    cs_current: dict | None = None
    awaiting_title = False

    for btype, obj in appendix_region:
        if btype == "para":
            text = obj.text.strip()
            style = obj.style.name if obj.style else ""

            if "Heading 1" in style:
                label_m = CS_LABEL_RE.match(text)
                if label_m:
                    if cs_current and cs_current.get("blocks"):
                        case_studies.append(cs_current)
                    cs_current = {"number": int(label_m.group(1)), "title": "", "blocks": []}
                    awaiting_title = True
                    continue
                elif awaiting_title and cs_current is not None:
                    cs_current["title"] = text.strip('"').strip("“”")
                    awaiting_title = False
                    continue

        if cs_current is not None and not awaiting_title:
            cs_current["blocks"].append((btype, obj))

    if cs_current and cs_current.get("blocks"):
        case_studies.append(cs_current)

    print(f"Case studies found  : {len(case_studies)}")

    # ── Split appendix ─────────────────────────────────────────────────────────
    appendix_sections: list[dict] = []
    app_current: dict | None = None

    for btype, obj in appendix_region:
        if btype == "para":
            text = obj.text.strip()
            style = obj.style.name if obj.style else ""

            if "Heading 2" in style and text:
                if app_current and app_current["blocks"]:
                    appendix_sections.append(app_current)
                app_current = {"title": text, "blocks": []}
                continue

            if "Heading 1" in style and CS_LABEL_RE.match(text):
                if app_current and app_current["blocks"]:
                    appendix_sections.append(app_current)
                app_current = None
                break

        if app_current is not None:
            app_current["blocks"].append((btype, obj))

    print(f"Appendix sections   : {len(appendix_sections)}")

    # ── Write files ────────────────────────────────────────────────────────────
    extracted_path.mkdir(parents=True, exist_ok=True)
    (extracted_path / "chapters").mkdir(exist_ok=True)
    (extracted_path / "case-studies").mkdir(exist_ok=True)
    (extracted_path / "appendix").mkdir(exist_ok=True)

    # front_quote.md
    if front_quote:
        (extracted_path / "front_quote.md").write_text(
            f"# Front Page Quote\n\n{front_quote}\n", encoding="utf-8"
        )
        print("✓ front_quote.md")
    else:
        print("⚠  No front quote located — verify QUOTE_START constant")

    # Chapter files
    chapter_manifest: list[dict] = []
    for ch in chapters:
        slug = f"chapter-{ch['number']:02d}-{slugify(ch['title'])}"
        body = blocks_to_markdown(ch["blocks"])
        wc = word_count(body)
        out = extracted_path / "chapters" / f"{slug}.md"
        out.write_text(
            f"# Chapter {ch['number']}: {ch['title']}\n\n{body}\n",
            encoding="utf-8",
        )
        chapter_manifest.append(
            {
                "number": ch["number"],
                "title": ch["title"],
                "slug": slug,
                "source_word_count": wc,
                "source_file": f"chapters/{slug}.md",
            }
        )

    print(f"✓ {len(chapters)} chapter files")

    # Case study files
    cs_manifest: list[dict] = []
    for cs in case_studies:
        slug = f"cliff-note-{cs['number']:03d}-{slugify(cs['title'])}"
        body = blocks_to_markdown(cs["blocks"])
        wc = word_count(body)
        out = extracted_path / "case-studies" / f"{slug}.md"
        out.write_text(
            f"# Cliff Note {cs['number']}: {cs['title']}\n\n{body}\n",
            encoding="utf-8",
        )
        cs_manifest.append(
            {
                "number": cs["number"],
                "title": cs["title"],
                "slug": slug,
                "source_word_count": wc,
                "source_file": f"case-studies/{slug}.md",
            }
        )

    print(f"✓ {len(case_studies)} case study files")

    # Appendix files
    for sec in appendix_sections:
        slug = slugify(sec["title"]) or "section"
        body = blocks_to_markdown(sec["blocks"])
        out = extracted_path / "appendix" / f"{slug}.md"
        out.write_text(f"# {sec['title']}\n\n{body}\n", encoding="utf-8")

    print(f"✓ {len(appendix_sections)} appendix files")

    # manifest.json
    manifest = {
        "codex_slug": codex_slug,
        "front_quote_present": bool(front_quote),
        "chapters": chapter_manifest,
        "case_studies": cs_manifest,
        "appendix_section_count": len(appendix_sections),
        "totals": {
            "chapters": len(chapter_manifest),
            "case_studies": len(cs_manifest),
            "total_chapter_words": sum(c["source_word_count"] for c in chapter_manifest),
            "total_cs_words": sum(c["source_word_count"] for c in cs_manifest),
        },
    }
    (extracted_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("✓ manifest.json")

    # full_outline.md
    lines = [f"# {cfg.get('codex_title', codex_slug)} — Full Outline\n"]
    lines.append("## Chapters\n")
    for ch in chapter_manifest:
        lines.append(
            f"- **Chapter {ch['number']}**: {ch['title']}  "
            f"({ch['source_word_count']:,} words)"
        )
    lines.append("\n## Cliff Note Case Studies\n")
    for cs in cs_manifest:
        lines.append(
            f"- **Cliff Note {cs['number']}**: {cs['title']}  "
            f"({cs['source_word_count']:,} words)"
        )
    (extracted_path / "full_outline.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print("✓ full_outline.md")

    # Summary
    t = manifest["totals"]
    print(
        f"\n✅ Extraction complete\n"
        f"   Chapters:           {t['chapters']}  ({t['total_chapter_words']:,} words)\n"
        f"   Case studies:       {t['case_studies']}  ({t['total_cs_words']:,} words)\n"
        f"   Appendix sections:  {manifest['appendix_section_count']}\n"
        f"   Front quote found:  {manifest['front_quote_present']}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract a .docx manuscript into organized markdown chunks."
    )
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()
    extract(args.config)
