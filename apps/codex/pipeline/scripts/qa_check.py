#!/usr/bin/env python3
"""
qa_check.py — Validate generated codex output against extracted source chunks.

Usage:
    python3 qa_check.py --config path/to/config.yaml

Reads:
    extracted/manifest.json         — word counts from extraction phase
    topics/{chapter-slug}.md        — generated topic files
    case-studies/{cs-slug}.md       — generated case-study files

Rules:
    - Every chapter in manifest must have a corresponding topic output file
    - Every case study in manifest must have a corresponding case-study output file
    - Output word count must be >= min_output_ratio * source word count (default 0.6)

Writes:
    qa_report.md                    — in the same directory as config.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pyyaml\nInstall with: pip install pyyaml")


# ── Data ───────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    kind: str          # "chapter" | "case-study"
    number: int
    title: str
    status: str        # "PASS" | "FAIL" | "MISSING"
    source_words: int
    output_words: int
    ratio: float
    output_path: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def word_count(text: str) -> int:
    return len(text.split())


def check_file(
    output_path: Path,
    source_words: int,
    min_ratio: float,
) -> tuple[str, int, float]:
    """Return (status, output_word_count, ratio)."""
    if not output_path.exists():
        return "MISSING", 0, 0.0
    text = output_path.read_text(encoding="utf-8")
    wc = word_count(text)
    ratio = wc / max(source_words, 1)
    status = "PASS" if ratio >= min_ratio else "FAIL"
    return status, wc, round(ratio, 3)


# ── Main ───────────────────────────────────────────────────────────────────────

def qa_check(config_path: str) -> int:
    cfg_path = Path(config_path).resolve()
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    extracted_path = (cfg_path.parent / cfg["extracted_path"]).resolve()
    output_base = (cfg_path.parent / cfg.get("course_output_path", ".")).resolve()
    min_ratio: float = cfg.get("pipeline", {}).get("min_output_ratio", 0.6)

    manifest_path = extracted_path / "manifest.json"
    if not manifest_path.exists():
        sys.exit(
            "ERROR: manifest.json not found.\n"
            "Run extract_manuscript.py --config <config> first."
        )

    with open(manifest_path) as f:
        manifest = json.load(f)

    topics_dir = output_base / "topics"
    cs_dir = output_base / "case-studies"

    results: list[CheckResult] = []

    # Check chapters → topics
    for ch in manifest["chapters"]:
        slug = ch["slug"]
        # The chapter worker writes the topic as the chapter slug
        out_path = topics_dir / f"{slug}.md"
        status, out_wc, ratio = check_file(out_path, ch["source_word_count"], min_ratio)
        results.append(
            CheckResult(
                kind="chapter",
                number=ch["number"],
                title=ch["title"],
                status=status,
                source_words=ch["source_word_count"],
                output_words=out_wc,
                ratio=ratio,
                output_path=str(out_path.relative_to(output_base)),
            )
        )

    # Check case studies
    for cs in manifest["case_studies"]:
        slug = cs["slug"]
        out_path = cs_dir / f"{slug}.md"
        status, out_wc, ratio = check_file(out_path, cs["source_word_count"], min_ratio)
        results.append(
            CheckResult(
                kind="case-study",
                number=cs["number"],
                title=cs["title"],
                status=status,
                source_words=cs["source_word_count"],
                output_words=out_wc,
                ratio=ratio,
                output_path=str(out_path.relative_to(output_base)),
            )
        )

    # ── Build report ─────────────────────────────────────────────────────────
    passing = [r for r in results if r.status == "PASS"]
    failing = [r for r in results if r.status in ("FAIL", "MISSING")]
    total = len(results)

    report_lines = [
        "# QA Report\n",
        f"**Config**: `{cfg_path.name}`  ",
        f"**Extracted from**: `{extracted_path}`  ",
        f"**Output base**: `{output_base}`  ",
        f"**Min output ratio**: {min_ratio} ({int(min_ratio * 100)}%)  \n",
        "## Summary\n",
        f"- Total checks: **{total}**",
        f"- Passing: **{len(passing)}**",
        f"- Failing / Missing: **{len(failing)}**\n",
    ]

    if failing:
        report_lines.append("## ❌ Failures\n")
        for r in failing:
            label = f"Chapter {r.number}" if r.kind == "chapter" else f"Cliff Note {r.number}"
            report_lines.append(f"### {label}: {r.title}")
            report_lines.append(f"- Status: **{r.status}**")
            report_lines.append(f"- Source: {r.source_words:,} words")
            report_lines.append(f"- Output: {r.output_words:,} words ({r.ratio:.0%})")
            report_lines.append(f"- Output file: `{r.output_path}`\n")
    else:
        report_lines.append("## ✅ All checks passed\n")

    report_lines.append("## Chapter Results\n")
    report_lines.append("| # | Title | Status | Source | Output | Ratio |")
    report_lines.append("|---|-------|--------|--------|--------|-------|")
    for r in results:
        if r.kind != "chapter":
            continue
        icon = "✅" if r.status == "PASS" else "❌"
        report_lines.append(
            f"| {r.number} | {r.title[:45]} | {icon} {r.status} "
            f"| {r.source_words:,} | {r.output_words:,} | {r.ratio:.0%} |"
        )

    report_lines.append("\n## Case Study Results\n")
    report_lines.append("| # | Title | Status | Source | Output | Ratio |")
    report_lines.append("|---|-------|--------|--------|--------|-------|")
    for r in results:
        if r.kind != "case-study":
            continue
        icon = "✅" if r.status == "PASS" else "❌"
        report_lines.append(
            f"| {r.number} | {r.title[:45]} | {icon} {r.status} "
            f"| {r.source_words:,} | {r.output_words:,} | {r.ratio:.0%} |"
        )

    report_text = "\n".join(report_lines) + "\n"
    report_path = cfg_path.parent / "qa_report.md"
    report_path.write_text(report_text, encoding="utf-8")

    if failing:
        print(f"\n❌ QA FAILED — {len(failing)}/{total} checks failing")
        print(f"   Report: {report_path}")
        return 1

    print(f"\n✅ QA PASSED — {len(passing)}/{total} checks passing")
    print(f"   Report: {report_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate codex output against extracted source."
    )
    parser.add_argument("--config", required=True, help="Path to config.yaml")
    args = parser.parse_args()
    sys.exit(qa_check(args.config))
