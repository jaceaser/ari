# How to Add a New Codex Course

This is the guide for launching a second (or third, or tenth) codex course. The engine is already built — adding a new course is purely a content and configuration exercise. No app code changes are required.

---

## Step 1 — Create the course directory

```bash
mkdir -p apps/codex/course-guides/<course-slug>/{topics,case-studies,operator-cards,glossary,pathways,documents,state-notes}
```

Use a lowercase, hyphenated slug that matches what buyers will see in the URL:
- `subject-to` → `codex.reilabs.ai/subject-to`
- `tax-liens` → `codex.reilabs.ai/tax-liens`
- `creative-finance` → `codex.reilabs.ai/creative-finance`

---

## Step 2 — Create course.config.yaml

```yaml
slug: <course-slug>
title: <Full Course Title>
description: >
  One to three sentence description shown on the course landing page.
productSlug: <course-slug>
version: "1.0"
featured:
  topics:
    - <slug-of-featured-topic-1>
    - <slug-of-featured-topic-2>
    - <slug-of-featured-topic-3>
  caseStudies:
    - <slug-of-case-study-1>
    - <slug-of-case-study-2>
  pathways:
    - <slug-of-pathway-1>
    - <slug-of-pathway-2>
```

The `productSlug` must exactly match what gets written to the user's `products[]` array in Cosmos when they purchase the course through Stripe. If these don't match, paying customers will be locked out.

---

## Step 3 — Create overview.md

```markdown
---
title: <Course Title> — Overview
---

Write 2–4 paragraphs introducing the course. This appears on the course landing page below the hero section. Focus on:
- What problem this course solves
- Who it's for
- What they'll be able to do after completing it
```

---

## Step 4 — Author topics

Each topic is a markdown file in `topics/`. Filename = slug.

**Minimum required frontmatter:**

```yaml
---
id: <slug>
slug: <slug>
title: <Title>
type: topic
summary: One sentence — shown on cards and search results.
tags: []
aliases: []
relatedNodes: []        # slugs of related entities (any type)
prerequisites: []       # slugs of topics that should be read first
searchTerms: []         # extra phrases for search (synonyms, plain language)
nextSteps: []           # slugs of topics to go to after this one
plainEnglish: >         # 1-2 sentences in plain language — shown in gold box at top of topic page
  ...
whyItMatters: >
  ...
whenUsed: >
  ...
applicabilitySignals: []
disqualifiers: []
risks: []
operatorNotes: >
  ...
estimatedReadTime: 8    # minutes
difficultyLevel: beginner  # beginner | intermediate | advanced
featured: false
order: 1
---

Full markdown body here. This becomes the main content block on the topic page.
```

**Tips:**
- `relatedNodes` accepts slugs of any entity type (topics, case studies, pathways, glossary terms, operator cards)
- `featured: true` on 3–5 topics makes them appear in the hero section of the course landing
- `order` controls the sequence in topic lists

---

## Step 5 — Author case studies

Each file in `case-studies/`:

```yaml
---
id: <slug>
slug: <slug>
title: <Title>
type: case-study
summary: One line describing the scenario and outcome.
tags: []
doctrines: []          # topic slugs that this case study illustrates
relatedNodes: []
featured: false
scenario: >
  What was the situation going in?
play: >
  What did the operator do?
outcome: >
  What happened?
takeaway: >
  The single most important lesson.
---

Extended narrative here if needed.
```

---

## Step 6 — Author operator cards

Each file in `operator-cards/`:

```yaml
---
id: <slug>
slug: <slug>
title: <Title> Checklist
type: operator-card
summary: One line describing what this card covers.
tags: []
relatedNodes: []
checklist:
  - Step one
  - Step two
  - Step three
commonMistakes:
  - Mistake one
  - Mistake two
scripts:
  - "Sample script or phrase if applicable"
---

Optional extended notes here.
```

---

## Step 7 — Author glossary terms

Each file in `glossary/`:

```yaml
---
id: <slug>
slug: <slug>
title: <Term>
type: glossary
definition: Precise legal or technical definition.
plainEnglish: >
  Plain-language version for someone who has never heard this term.
relatedTerms: []       # slugs of related glossary terms
aliases: []
tags: []
summary: One sentence — same as definition but shorter.
searchTerms: []
---
```

---

## Step 8 — Author pathways

Each file in `pathways/`:

```yaml
---
id: <slug>
slug: <slug>
title: <Pathway Name>
type: pathway
summary: What situation this pathway is for.
entryCondition: >
  The exact situation a user is in when they start this pathway.
tags: []
likelyDocuments: []
stateSensitivity: >
  Any important state-by-state variation.
relatedNodes: []
featured: false
steps:
  - order: 1
    topicSlug: <topic-slug>
    label: What you do in this step
    decisionPoints:
      - Question or branch point the operator faces here
    risks:
      - What can go wrong here
  - order: 2
    topicSlug: <topic-slug>
    label: Next step
---
```

---

## Step 9 — Wire up entitlement in apps/api

When the course is ready to go live, two things need to happen in `apps/api`:

1. **Add a Stripe Product** for the course. In the product metadata, set:
   ```
   codex_course: <course-slug>
   ```
   This is what the webhook reads to know which course was purchased.

2. **Verify the webhook handler** writes `<course-slug>` to the user's `products[]` array in Cosmos when a checkout session for this product completes. The entitlement check in `apps/codex/lib/entitlements.ts` reads this array directly — no other config needed.

---

## Step 10 — Deploy

The codex app reads content from the filesystem at runtime. A new course requires a **rebuild and redeploy** of the codex Docker image:

```bash
cd apps/codex
az acr build -r ariprodacr -t ari-codex:latest .
az webapp restart -g rg-ari-prod -n ari-codex
```

That's it. The new course is live at `codex.reilabs.ai/<course-slug>`.

---

## Content quality checklist before launch

- [ ] All `relatedNodes` slugs actually exist (broken links show nothing, not errors — but they should be clean)
- [ ] At least 3 topics marked `featured: true` for the landing page hero
- [ ] At least 2 case studies and 2 pathways created
- [ ] At least 8 glossary terms
- [ ] `productSlug` in course.config.yaml matches the Stripe product metadata exactly
- [ ] `course-slug` in directory name matches `slug` in course.config.yaml
- [ ] All topic bodies have content (not just frontmatter)
- [ ] `estimatedReadTime` and `difficultyLevel` filled in on all topics (used in sidebar)

---

## Example course slugs for future codexes

| Course | Slug | Product Tag |
|--------|------|-------------|
| Subject-To | `subject-to` | `subject-to` |
| Tax Liens & Deeds | `tax-liens` | `tax-liens` |
| Creative Finance | `creative-finance` | `creative-finance` |
| Note Investing | `note-investing` | `note-investing` |
| Commercial RE | `commercial-re` | `commercial-re` |
