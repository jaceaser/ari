# 03 — Landing Page

You are building the landing page configuration for a codex course.

## Task

Update `course.config.yaml` and `overview.md` so the landing page displays:
1. The manuscript's front-page quote, prominently
2. A full, compelling course description drawn from the manuscript's preface
3. The correct featured content (topics, case studies, pathways)

---

## Step 1 — Read source material

Read:
- `extracted/front_quote.md` — the pull quote
- `extracted/manifest.json` — chapter and case study list
- `extracted/full_outline.md` — complete outline
- Current `course.config.yaml`

---

## Step 2 — Update course.config.yaml

Add `frontPageQuote` and `frontPageQuoteAttribution` fields.  
Update the `featured` section to reference real chapter slugs from the manifest.

The updated config must look like:

```yaml
slug: {{codex_slug}}
title: {{codex_title}}
description: >
  <2-3 sentence description of the course. Describe what operators will be able to DO after 
  completing it. Draw from the manuscript's preface — not generic course-description language.>
productSlug: {{codex_slug}}
version: "1.0"
frontPageQuote: |
  <exact text from extracted/front_quote.md — the four-line quote block, without blockquote markers>
frontPageQuoteAttribution: '<attribution from front_quote.md>'
featured:
  topics:
    - <slug of the most foundational chapter — e.g. chapter-01-the-strategy-in-one-sentence>
    - <slug of the most commonly needed chapter>
    - <slug of the chapter that shows the system's uniqueness>
  caseStudies:
    - <slug of the most compelling case study>
    - <slug of the most instructive case study>
    - <slug of the most surprising case study>
  pathways:
    - <slug of the highest-traffic scenario pathway>
    - <slug of the most complex scenario pathway>
```

**Rules**:
- `frontPageQuote` must be the exact text from `front_quote.md`, without `>` blockquote markers
- `frontPageQuoteAttribution` must include the em dash: `— Charles "Uncle Charles" Hernandez`
- All `featured` slugs must exist in the manifest
- Do not invent slugs

---

## Step 3 — Update overview.md

The overview appears on the course landing page below the quote and hero section.  
It should draw from the manuscript's preface/foreword.

Write 4-6 paragraphs that:
1. State what fractured equity is and why the opportunity exists
2. Describe the operator who masters this system (what they can do that others can't)
3. Name the specific legal tools the course covers
4. Set expectations honestly (this is not easy; it requires careful work)
5. Close with a statement of what the course delivers

Voice: Uncle Charles' direct, unpretentious, first-person voice. Not marketing copy.

The overview should be 400-600 words total.

---

## Step 4 — Verify

After writing both files:
1. Read `course.config.yaml` and confirm `frontPageQuote` is present
2. Confirm all `featured` slugs exist as files in `topics/` or `case-studies/`
3. Confirm `overview.md` is 400-600 words

Report: what was changed, what the front quote text is (first line), and how many featured items are set.
