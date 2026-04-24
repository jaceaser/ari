# ARI Codex — Content Pipeline

Converts any `.docx` manuscript into a comprehensive interactive course (a "codex").
The pipeline is reusable — drop a new manuscript into `course-guides/{slug}/` and run the same steps.

---

## Architecture

```
pipeline/
├── scripts/
│   ├── extract_manuscript.py   ← parse docx → raw markdown chunks
│   └── qa_check.py             ← validate output word counts + coverage
├── prompts/
│   ├── 00_orchestrator.md      ← coordinates all phases
│   ├── 01_extract.md           ← runs extraction, reports manifest
│   ├── 02_chapter_worker.md    ← single-chapter or case-study subagent
│   ├── 03_landing_page.md      ← builds course.config.yaml + overview.md
│   └── 04_qa.md                ← runs qa_check.py, fixes failures
└── templates/
    ├── topic_template.md       ← frontmatter + body structure for topics
    └── case_study_template.md  ← frontmatter + body structure for case-studies
```

The content lives under `course-guides/{slug}/` and is read at runtime by the Next.js app.

---

## Adding a New Codex

### 1. Create the course directory

```bash
mkdir -p apps/codex/course-guides/{new-slug}/{topics,case-studies,operator-cards,glossary,pathways}
```

Place the manuscript `.docx` in the new directory.

### 2. Create config.yaml

Copy `pipeline/config.example.yaml` into the new course directory as `config.yaml`.  
Fill in all values — especially:
- `codex_slug` — must match the directory name
- `manuscript_path` — relative path to the .docx
- `front_page_quote` — the opening pull quote from the manuscript
- `manuscript_structure` settings — verify the heading styles match your docx

### 3. Create course.config.yaml

Copy `course-guides/fractured-equity/course.config.yaml` as a template.  
Update: slug, title, description, productSlug.  
Leave `frontPageQuote` blank — `03_landing_page.md` will fill it in.

### 4. Run the pipeline

Invoke `00_orchestrator.md` from a Claude conversation, passing the config path:

```
Run the codex pipeline orchestrator at apps/codex/pipeline/prompts/00_orchestrator.md
Config: apps/codex/course-guides/{new-slug}/config.yaml
```

The orchestrator will:
1. Run extraction → show manifest summary for approval
2. Back up any existing content
3. Update the landing page config
4. Spawn chapter workers in parallel batches of 8
5. Spawn case study workers in parallel batches of 8
6. Run QA and iterate on failures

### 5. Review qa_report.md

The QA check verifies:
- Every chapter in the manifest has a corresponding `topics/{slug}.md` file
- Every case study has a corresponding `case-studies/{slug}.md` file
- Each output file is at least 60% of the source word count

Address any failures before deploying.

### 6. Deploy

```bash
cd apps/codex
az acr build -r ariprodacr -t ari-codex:latest .
az webapp restart -g rg-ari-prod -n ari-codex
```

---

## The 60% Rule

QA flags any output file whose word count is less than 60% of the corresponding source chunk.  
This rule exists because the primary failure mode of AI-generated course content is over-condensation —
taking a 2,000-word chapter and producing a 300-word summary that strips out the case studies,
numbered steps, and technical detail that make the content actually useful.

If QA flags a chapter, re-run its worker with an explicit instruction to expand.  
"More pages is fine; brevity is not the goal" — the chapter worker prompt is designed to enforce this.

---

## Manuscript Structure Requirements

The extractor assumes this document structure (based on the Fractured Equity manuscript):

| Content | Detection |
|---------|-----------|
| Chapter headings | `Normal` style paragraphs matching `^CHAPTER \d+$` |
| Chapter sub-sections | `SecHead` style paragraphs |
| Case study labels | `Heading 1` matching `^CLIFF NOTE CASE STUDY \d+$` |
| Case study titles | `Heading 1` immediately after the label |
| Appendix sections | `Heading 2` |
| Front page quote | Normal paragraph containing `"Every chapter in this Codex is a door"` |

If a future manuscript uses different heading styles, adjust `CHAPTER_HEADING_RE`,
`CS_LABEL_RE`, and `QUOTE_START` at the top of `extract_manuscript.py`.

---

## Requirements

```bash
pip install python-docx pyyaml
```

Python 3.10+ required.
