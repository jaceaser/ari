# Admin Portal — Dynamic Course Upload

## Status: Not yet built. Spec only.

This describes the future admin portal that allows uploading a DOCX manuscript and having the system automatically create a course — without a rebuild or redeploy.

---

## The Problem It Solves

Today (file-based v1), adding a new codex requires:
1. Manually converting DOCX content to markdown
2. Authoring frontmatter for every entity
3. Rebuilding and redeploying the Docker image

The admin portal eliminates all three steps. An operator uploads a DOCX, the system extracts and structures the content with AI assistance, and the course appears live without touching code or infrastructure.

---

## What Changes Architecturally

### Today (file-based)

```
DOCX → manually authored markdown files → filesystem → content-loader.ts → page
```

### With admin portal

```
DOCX → upload → AI extraction pipeline → Cosmos DB / Azure Blob → content-loader.ts (updated) → page
```

The content loader needs one change: instead of reading only from the filesystem, it checks Cosmos/Blob first, falls back to filesystem. File-based courses keep working. DB-backed courses work without a rebuild.

---

## Storage Design

### Azure Cosmos DB — course registry + entity metadata

New container: `codex_courses`

```json
{
  "id": "subject-to",
  "slug": "subject-to",
  "title": "Subject-To Codex",
  "productSlug": "subject-to",
  "version": "1.0",
  "status": "draft | published | archived",
  "source": "upload | filesystem",
  "createdAt": "...",
  "publishedAt": "...",
  "featured": { "topics": [], "caseStudies": [], "pathways": [] }
}
```

New container: `codex_entities`

```json
{
  "id": "subject-to::topic::subject-to-basics",
  "courseSlug": "subject-to",
  "slug": "subject-to-basics",
  "type": "topic",
  "title": "Subject-To Basics",
  "body": "<rendered HTML>",
  "frontmatter": { ... all entity fields ... },
  "status": "draft | published"
}
```

Partition key: `courseSlug`. This means all entities for one course are co-located and a full course load is one efficient query.

### Azure Blob Storage — original DOCX + extracted assets

Container: `codex-uploads`

```
codex-uploads/
  <course-slug>/
    original.docx
    extracted/
      chapter-01.txt
      chapter-02.txt
      ...
```

---

## DOCX Extraction Pipeline

### Step 1 — Parse structure

Use `python-docx` (already available in the environment) on the API side:
- Extract all paragraphs with their heading levels
- Identify chapter boundaries by `CHAPTER N` headings
- Extract lists, tables, and formatted blocks separately

### Step 2 — AI entity extraction (Claude)

Send each chapter to Claude with a structured prompt:

```
Given this chapter from a real estate knowledge book, extract the following as JSON:
- title
- type (topic | case-study | pathway | operator-card | glossary | none)
- summary (one sentence)
- plainEnglish (1-2 sentences, plain language)
- whyItMatters
- whenUsed
- risks (array)
- relatedConcepts (array of concept names — will be resolved to slugs)
- body (cleaned markdown of the chapter)

Chapter content:
[chapter text]
```

Claude returns structured JSON. The pipeline validates it, assigns slugs, resolves `relatedConcepts` to actual slugs within the course, and writes to Cosmos.

### Step 3 — Human review in admin portal

The extracted entities appear in a draft state in the admin portal. The admin can:
- Edit any field
- Merge or split entities
- Add missing frontmatter
- Mark entities as published one by one or all at once
- Preview exactly how each page will look before publishing

### Step 4 — Publish

Admin clicks "Publish Course". All entities flip to `status: published`. The course appears at `codex.reilabs.ai/<course-slug>` immediately — no rebuild.

---

## Admin Portal UI

A protected route inside `apps/codex` at `/admin`:

```
/admin                          → course list + upload new
/admin/[course]                 → course overview, publish controls
/admin/[course]/entities        → full entity list with status
/admin/[course]/entities/[id]   → entity editor (markdown + frontmatter)
/admin/[course]/preview         → preview the course as a user sees it
```

### Authentication

Admin portal uses the same NextAuth session as the rest of the app. Only users with `role: admin` in their Cosmos doc can access `/admin`. Add middleware guard:

```typescript
// middleware.ts — extend existing auth check
if (request.nextUrl.pathname.startsWith('/admin')) {
  if (!session?.user?.isAdmin) return redirect('/');
}
```

### Upload flow

1. Admin drops a DOCX file onto the upload area
2. File is sent to `/api/admin/upload` route handler
3. Route handler:
   a. Saves DOCX to Azure Blob Storage
   b. Triggers the extraction pipeline (can be sync for small files, async job for large ones)
   c. Returns a job ID
4. Admin portal polls job status and shows progress
5. When complete, redirects to `/admin/[course]/entities` for review

---

## Updated Content Loader

The only code change needed to the existing app:

```typescript
// lib/content-loader.ts — add DB source

export async function loadCourse(slug: string): Promise<Course> {
  // Check Cosmos first
  const dbCourse = await loadCourseFromDb(slug);
  if (dbCourse) return dbCourse;

  // Fall back to filesystem (existing file-based courses)
  return loadCourseFromFilesystem(slug);
}
```

File-based courses (fractured-equity) keep working exactly as today. New courses uploaded via the portal come from Cosmos. Zero regression risk.

---

## Azure Resources Needed

| Resource | Purpose |
|----------|---------|
| Cosmos DB container `codex_courses` | Course registry |
| Cosmos DB container `codex_entities` | Entity storage |
| Azure Blob container `codex-uploads` | DOCX originals + extracted text |
| Azure Queue (optional) | For async extraction jobs on large files |

All of these can live in the existing `db-uc-ai` Cosmos account and the existing storage account — no new Azure resources required.

---

## Extraction Quality Notes

Claude handles the entity extraction well for well-structured DOCX files. Quality degrades for:
- Books with inconsistent heading structure
- Chapters that span multiple entity types (need splitting)
- Heavy use of tables (need special handling)
- Appendices (often better treated as operator cards or documents rather than topics)

For the best results, source manuscripts should follow a structured format similar to the Fractured Equity Codex — numbered chapters with clear section headers.

---

## Build Sequence

When this gets built, the recommended order is:

1. Add Cosmos containers (`codex_courses`, `codex_entities`)
2. Update content-loader.ts to check Cosmos before filesystem
3. Build admin portal upload + job tracking UI
4. Build DOCX extraction pipeline (python-docx + Claude)
5. Build entity editor in admin portal
6. Build publish controls
7. Add `/admin` middleware guard

This can ship incrementally — step 1+2 alone enable manually-entered DB courses without the upload pipeline.

---

## Related Files

- `CODEX.md` — full codex app spec
- `NEW_CODEX.md` — how to add a course today (file-based approach)
- `PROGRESS.md` — build status
