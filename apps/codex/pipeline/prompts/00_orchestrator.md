# 00 — Orchestrator

You are the pipeline orchestrator for the ARI Codex content generation system.  
Your job is to coordinate all phases to convert a manuscript into a complete interactive course.

## Config

You will be given a path to `config.yaml` inside a `course-guides/{slug}/` folder.  
All paths in prompts are relative to that config file unless noted otherwise.

**Config path given**: `{{config_path}}`

---

## Phase Sequence

### Phase 1 — Extract
Invoke prompt `01_extract.md` with `--config {{config_path}}`.  
Wait for the manifest summary before proceeding.  
Confirm:
- Front quote was found
- Chapter count matches expected (should be 42 for Fractured Equity)
- Case study count matches expected (should be 100 for Fractured Equity)

If anything is wrong, stop and report before continuing.

---

### Phase 2 — Back up existing content
Before generating any output files, back up the current course content:

```bash
cp -r {{course_output_path}}/topics    {{course_output_path}}/topics.bak
cp -r {{course_output_path}}/case-studies  {{course_output_path}}/case-studies.bak
cp -r {{course_output_path}}/pathways  {{course_output_path}}/pathways.bak
cp -r {{course_output_path}}/operator-cards  {{course_output_path}}/operator-cards.bak
cp -r {{course_output_path}}/glossary  {{course_output_path}}/glossary.bak
cp    {{course_output_path}}/overview.md  {{course_output_path}}/overview.bak.md
cp    {{course_output_path}}/course.config.yaml  {{course_output_path}}/course.config.bak.yaml
```

Confirm backup succeeded before overwriting any files.

---

### Phase 3 — Landing page
Invoke prompt `03_landing_page.md` with the config path.  
This updates `course.config.yaml` with the front quote and updates `overview.md`.

---

### Phase 4 — Chapter workers (parallel batches of 8)

Read `extracted/manifest.json`.  

For **each chapter** (42 total for Fractured Equity), spawn a fresh subagent using prompt `02_chapter_worker.md`.  
Run in **parallel batches of {{pipeline.parallel_chapter_batch_size}}** (default: 8).

Pass each worker:
- Chapter number
- Chapter slug (from manifest)
- Chapter source file path: `extracted/chapters/{slug}.md`
- Full outline path: `extracted/full_outline.md`
- Output path: `topics/{slug}.md`
- Config path

Wait for each batch to complete before starting the next.  
Report any worker failures immediately.

---

### Phase 5 — Case study workers (parallel batches of 8)

For **each case study** (100 total for Fractured Equity), spawn a fresh subagent using prompt `02_chapter_worker.md` in case-study mode.

Pass each worker:
- Case study number and title
- Source file: `extracted/case-studies/{slug}.md`
- Output path: `case-studies/{slug}.md`
- Config path

Run in parallel batches of {{pipeline.parallel_chapter_batch_size}}.

---

### Phase 6 — QA
Invoke prompt `04_qa.md` with the config path.  
Show the full `qa_report.md` content.  
For any FAIL or MISSING items, re-invoke the corresponding chapter or case study worker.  
Repeat until QA passes (all checks green) or you've made 3 attempts per failing item.

---

## Rules

- Never overwrite files until the backup is confirmed
- Never skip a chapter or case study — 42 + 100 = 142 output files are required
- Never summarize: if a worker produces < 60% of source word count, re-run it with explicit instruction to expand
- Report progress after each batch (e.g., "Batch 2/6 complete: 16/42 chapters done")
- If any phase fails catastrophically, stop and report the error in full
