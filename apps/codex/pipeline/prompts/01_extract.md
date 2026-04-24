# 01 — Extract Manuscript

You are running the extraction phase of the ARI Codex pipeline.

## Task

Run `extract_manuscript.py` and report the manifest summary.

```bash
cd apps/codex/course-guides/{{config.codex_slug}}
python3 ../../pipeline/scripts/extract_manuscript.py --config config.yaml
```

## After the script completes, report:

1. **Chapter count** — should match expected (e.g., 42 for Fractured Equity)
2. **Case study count** — should match expected (e.g., 100 for Fractured Equity)
3. **Front quote found** — yes/no, and if yes, show the quote text
4. **Appendix section count**
5. **Total chapter word count** and **total case study word count**
6. **Any errors or warnings** printed during extraction

Then show the first 10 entries of `extracted/full_outline.md` (chapters) and the first 5 case study entries so the operator can confirm the content looks correct.

## If the script fails:

Report the exact error and traceback. Common fixes:
- Missing `python-docx` or `pyyaml`: `pip install python-docx pyyaml`
- Wrong manuscript path: check `manuscript_path` in config.yaml
- Chapter marker not found: verify `CHAPTER_HEADING_RE` matches the actual heading text (open docx and check)

## Success criteria

- Chapter count ≥ 40 (42 expected for Fractured Equity)
- Case study count ≥ 90 (100 expected for Fractured Equity)
- Front quote present
- `manifest.json` written to `extracted/`
- `full_outline.md` written to `extracted/`
- All chapter and case study files written

Do not proceed to Phase 3 until these criteria are confirmed.
