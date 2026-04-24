# ARI Codex Engine — Build Specification

## Overview

Build a production-style, mobile-first and desktop-ready codex application inside `/apps/codex`.

**This is NOT a chatbot app.**
Do not build a ChatGPT-style interface.
Do not make the homepage a chat box.
This must feel like an interactive knowledge system, visual thinking map, and guided learning engine.

---

## Primary Goal

Build a reusable Codex Engine for ARI that can power premium knowledge products and courses. The first implementation is the **Fractured Equity Codex**, but the app must be built so future codexes can be added by creating another course folder under:

```
/apps/codex/course-guides/<course-slug>
```

This is not a one-off static site. It must be content-driven, course-aware, and designed for long-term scale.

---

## Product Context

ARI already has authentication and entitlement logic. This codex app must integrate with the same auth token/session approach ARI is already using and must check the database to determine whether the current user has access to a given codex product.

**Codex courses are separate purchasable products, not tier perks.** Do NOT gate access by tier (`elite`, `pro`, `lite`) — that model is for ARI's AI features, not for individually sold knowledge products. A user on the `pro` tier who has not purchased Fractured Equity must be blocked. A user on the `lite` tier who has purchased Fractured Equity must be allowed in. Tier and course ownership are completely independent.

### Entitlement Model

Each codex course has a `products` slug (e.g., `fractured-equity`, `subject-to`). Ownership is stored as a `products: string[]` array on the user's Cosmos document:

```json
{
  "id": "...",
  "email": "...",
  "tier": "pro",
  "products": ["fractured-equity"]
}
```

Access check: `products.includes(courseSlug)`.

This means:
- Buying `fractured-equity` grants `/fractured-equity/*` only
- It does not grant `/subject-to/*` or any other course
- Two users can both be `pro` tier — one with a codex purchase, one without

### Required Backend Changes (apps/api)

Before the codex app can go live, `apps/api` needs two additions:

1. **`products[]` field in Cosmos user docs** — add when empty, append on purchase. The Python functions that read user docs must return this field.

2. **`GET /auth/user-products` endpoint** — returns `{ products: string[] }` for the authenticated user. This is what the codex app calls to check access. Implement with the same JWT auth middleware already used on other protected routes.

3. **Stripe webhook handling for codex purchases** — when a Stripe checkout session completes for a codex product, add the course slug to `products[]` in Cosmos. Map Stripe Product metadata (`codex_course: fractured-equity`) to the slug. Add this to the existing webhook handler in `apps/api`.

The codex app must not implement its own Stripe integration — it only reads the result (the `products[]` array).

### Entitlement Abstraction

Implement in `lib/entitlements.ts`:

```typescript
export async function checkEntitlement(
  userId: string,
  courseSlug: string
): Promise<boolean> {
  // Calls GET /auth/user-products on apps/api (server-side only)
  const products = await getUserProducts(userId);
  return products.includes(courseSlug);
}
```

All route protection calls this function. If the backend changes how products are stored, only this function changes — calling code is unaffected.

Do not hardcode entitlements only in the frontend. The access check must be server-side (server component or route handler), never client-side only.

---

## Important: Apps Are Self-Contained

ARI has no shared `packages/` directory. `apps/codex` cannot import from `apps/web`. The following must be copied/recreated inside `apps/codex`:

- NextAuth config — mirror the pattern from `apps/web/app/(auth)/auth.ts`
- CSS design tokens — copy the `globals.css` CSS variable block (ARI gold, dark mode, sidebar tokens, etc.)
- shadcn/ui components needed by the codex UI
- Any auth helper utilities needed

Inspect `apps/web` before building to extract these. Do not invent a disconnected auth or design system.

---

## Design / Branding

Use ARI theme colors and design language. The UI should feel premium, authoritative, modern, and consistent with ARI. Use the established theme palette — do not introduce a new visual identity.

**ARI primary color:** `hsl(41 92% 67%)` (ARI gold, `--ari-gold`)
**Dark background:** `hsl(0 0% 5%)`
**Card background (dark):** `hsl(0 0% 7%)`

Visual direction:
- ARI theme colors (gold primary, dark-first)
- Clean premium layout
- Strong typography
- Card-based sections
- Smooth transitions
- Mobile-first, desktop-ready
- Readable, fast, uncluttered
- Premium operator/legal-strategy feel

---

## Tech Stack

- **React** + **TypeScript**
- **Next.js App Router** (App Router only, no Pages Router)
- **Tailwind CSS v4** — inline CSS variables in `globals.css`, no `tailwind.config.ts`. Match the pattern used in `apps/web/app/globals.css`
- **shadcn/ui** — copy components from `apps/web/components/ui/` as needed
- **Framer Motion** — subtle transitions
- **`@xyflow/react` v12** — knowledge map (this is the correct package name; `react-flow` is outdated)
- **NextAuth v5 (beta)** — auth, same version as `apps/web`
- **gray-matter** + **remark/rehype** — markdown parsing with frontmatter

Follow existing monorepo conventions. Do not add a root `package.json` or workspace config — this app is self-contained like all other apps in this monorepo.

---

## Azure Deployment

This app is hosted on **Azure App Service as a Docker container**, following the same pattern as `apps/web`. Do not set up Vercel or any other host.

### Docker

Add a `Dockerfile` to `apps/codex` mirroring `apps/web/Dockerfile`. Use multi-stage build with standalone Next.js output.

Required `next.config.ts`:
```typescript
output: 'standalone'
```

### ACR Image Tags
- Production: `ariprodacr.azurecr.io/ari-codex:latest`
- Dev: `ariprodacr.azurecr.io/ari-codex:dev`

### App Service Names
- Production: `ari-codex` in resource group `rg-ari-prod`
- Dev: `ari-codex-dev` in resource group `rg-ari-dev`

### Custom Domain
- Production: `https://codex.reilabs.ai` → CNAME to `ari-codex.azurewebsites.net`
- Dev: `https://ari-codex-dev.azurewebsites.net` (no custom domain for dev)

Configure the custom domain in Azure:
```bash
az webapp config hostname add \
  --resource-group rg-ari-prod \
  --webapp-name ari-codex \
  --hostname codex.reilabs.ai
# Then add a CNAME record: codex.reilabs.ai → ari-codex.azurewebsites.net
# Enable managed TLS:
az webapp config ssl bind \
  --resource-group rg-ari-prod \
  --name ari-codex \
  --hostname codex.reilabs.ai \
  --ssl-type SNI
```

### Fallback Subdomains
- Production: `https://ari-codex.azurewebsites.net`
- Dev: `https://ari-codex-dev.azurewebsites.net`

### Required Environment Variables
```
AUTH_SECRET=<same or separate secret>
AUTH_TRUST_HOST=true
AUTH_URL=https://codex.reilabs.ai
NEXTAUTH_URL=https://codex.reilabs.ai
API_URL=https://reilabs-ari-api.azurewebsites.net
WEBSITES_ENABLE_APP_SERVICE_STORAGE=false
```

### Build Commands
```bash
# From apps/codex:
# Dev
az acr build -r ariprodacr -t ari-codex:dev \
  --build-arg NEXT_PUBLIC_API_URL=https://ari-api-dev.azurewebsites.net .
az webapp restart -g rg-ari-dev -n ari-codex-dev

# Prod
az acr build -r ariprodacr -t ari-codex:latest \
  --build-arg NEXT_PUBLIC_API_URL=https://reilabs-ari-api.azurewebsites.net .
az webapp restart -g rg-ari-prod -n ari-codex
```

> NOTE: Any `NEXT_PUBLIC_*` env vars are baked into the image at build time. Changing them in App Service settings has no effect — always rebuild the image.

---

## Routing

`apps/codex` is a standalone Next.js app deployed at its own subdomain. Routes are relative to that domain.

```
/                              → course listing or redirect to first course
/[course]                      → course landing page
/[course]/topic/[slug]
/[course]/case-study/[slug]
/[course]/pathway/[slug]
/[course]/glossary
/[course]/glossary/[slug]
/[course]/operator/[slug]
/[course]/document/[slug]
/[course]/map
```

Examples at `codex.reilabs.ai`:
- `/fractured-equity`
- `/fractured-equity/topic/partition-action`
- `/fractured-equity/pathway/co-owner-wont-sell`
- `/fractured-equity/map`

Do not hardcode only one course into the route structure. All course-specific routes must use `[course]` as a dynamic segment.

---

## Repository / App Structure

```
apps/codex/
├── Dockerfile
├── package.json
├── tsconfig.json
├── next.config.ts
├── postcss.config.mjs
├── app/
│   ├── layout.tsx                    ← root layout, SessionProvider, ThemeProvider
│   ├── globals.css                   ← ARI design tokens (copied from apps/web)
│   ├── (auth)/
│   │   ├── auth.ts                   ← NextAuth config (mirrored from apps/web)
│   │   ├── auth.config.ts
│   │   └── login/page.tsx
│   ├── [course]/
│   │   ├── page.tsx                  ← course landing
│   │   ├── layout.tsx                ← course layout (entitlement gate)
│   │   ├── topic/[slug]/page.tsx
│   │   ├── case-study/[slug]/page.tsx
│   │   ├── pathway/[slug]/page.tsx
│   │   ├── glossary/
│   │   │   ├── page.tsx
│   │   │   └── [slug]/page.tsx
│   │   ├── operator/[slug]/page.tsx
│   │   ├── document/[slug]/page.tsx
│   │   └── map/page.tsx
│   └── api/
│       ├── auth/[...nextauth]/route.ts
│       └── entitlement/[course]/route.ts
├── components/
│   ├── ui/                           ← shadcn/ui components
│   ├── codex/
│   │   ├── CourseHero.tsx
│   │   ├── TopicPage.tsx
│   │   ├── KnowledgeMap.tsx
│   │   ├── PathwayView.tsx
│   │   ├── CaseStudyView.tsx
│   │   ├── OperatorCard.tsx
│   │   ├── GlossaryView.tsx
│   │   ├── SearchBar.tsx
│   │   ├── Breadcrumb.tsx
│   │   ├── LockedCourse.tsx
│   │   └── RecentHistory.tsx
├── lib/
│   ├── content-loader.ts             ← markdown parser, entity normalizer
│   ├── graph-builder.ts              ← builds relationship graph from content
│   ├── search-index.ts               ← search index builder
│   ├── entitlements.ts               ← checkEntitlement() abstraction
│   └── api-client.ts                 ← calls to apps/api backend
├── types/
│   └── codex.ts                      ← content entity types/schemas
├── middleware.ts                     ← auth guard
└── course-guides/
    └── fractured-equity/
        ├── course.config.yaml
        ├── overview.md
        ├── topics/
        ├── case-studies/
        ├── operator-cards/
        ├── glossary/
        ├── pathways/
        ├── documents/
        └── state-notes/
```

---

## Auth / Access Pattern

### Authentication

Mirror the NextAuth v5 setup from `apps/web/app/(auth)/auth.ts`:
- Same magic-link + JWT flow
- Session extended with `id` (userId) and `type` (guest | regular)
- Server components use `const session = await auth()`
- Guests are redirected to login; unauthenticated users are redirected to login

### Entitlement Check

The codex app calls the new `GET /auth/user-products` endpoint on `apps/api` (see Backend Changes section above). This returns the array of course slugs the user has purchased.

`lib/entitlements.ts`:

```typescript
export async function getUserProducts(userId: string): Promise<string[]> {
  // Server-side call to apps/api — never exposed to client
  const res = await fetch(`${process.env.API_URL}/auth/user-products`, {
    headers: { Authorization: `Bearer ${await mintJwt(userId)}` },
    next: { revalidate: 60 }, // cache 60s — product purchases are infrequent
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.products ?? [];
}

export async function checkEntitlement(
  userId: string,
  courseSlug: string
): Promise<boolean> {
  const products = await getUserProducts(userId);
  return products.includes(courseSlug);
}
```

The check is per-course and per-user. Tier is irrelevant to codex access.

### Route Protection

In the `[course]/layout.tsx`, check entitlement server-side:

```typescript
const session = await auth();
if (!session?.user || session.user.type === 'guest') redirect('/login');
const hasAccess = await checkEntitlement(session.user.id, params.course);
if (!hasAccess) return <LockedCourse course={params.course} />;
```

Do not expose any course content to users who fail this check.

---

## Content System

### Source Material

There is an existing source manuscript at:
```
/apps/codex/course-guides/fractured-equity/MASTER CODEX MANUSCRIPT.docx
```

Extract and convert relevant sections from this manuscript into the markdown file structure described below rather than writing all content from scratch. The manuscript is the authoritative source for Fractured Equity content.

### Authoring Format

All content is markdown files with YAML frontmatter. The content loader derives routes, graph relationships, search index entries, and breadcrumbs from metadata — not from folder structure alone.

### Content Loader

Implement `lib/content-loader.ts` that:
1. Reads all markdown files under `course-guides/<course-slug>/`
2. Parses frontmatter with `gray-matter`
3. Renders body with `remark` / `rehype`
4. Normalizes each file into a typed entity (Topic, CaseStudy, etc.)
5. Returns a structured course object with all entities indexed by slug

---

## Frontmatter / Entity Types

Define types in `types/codex.ts`.

### Base fields (all entities)

```typescript
interface CodexEntity {
  id: string;
  slug: string;
  title: string;
  type: 'topic' | 'case-study' | 'operator-card' | 'glossary' | 'pathway' | 'document' | 'state-note';
  summary: string;
  tags: string[];
  aliases: string[];
  relatedNodes: string[];       // slugs
  prerequisites: string[];      // slugs
  searchTerms: string[];
  order?: number;
  featured?: boolean;
  stateScope?: string[];        // e.g. ['TX', 'FL'] or ['all']
  entitlementTag?: string;      // override course-level entitlement if needed
  body: string;                 // rendered HTML
}
```

### Topic (extends base)

```typescript
interface Topic extends CodexEntity {
  type: 'topic';
  plainEnglish: string;
  whyItMatters: string;
  whenUsed: string;
  applicabilitySignals: string[];
  disqualifiers: string[];
  risks: string[];
  nextSteps: string[];          // slugs
  operatorNotes: string;
  estimatedReadTime: number;    // minutes
  difficultyLevel: 'beginner' | 'intermediate' | 'advanced';
}
```

### Case Study (extends base)

```typescript
interface CaseStudy extends CodexEntity {
  type: 'case-study';
  scenario: string;
  doctrines: string[];          // topic slugs involved
  play: string;
  outcome: string;
  takeaway: string;
}
```

### Pathway (extends base)

```typescript
interface Pathway extends CodexEntity {
  type: 'pathway';
  entryCondition: string;
  steps: PathwayStep[];
  likelyDocuments: string[];    // document slugs
  stateSensitivity: string;
}

interface PathwayStep {
  order: number;
  topicSlug: string;
  label: string;
  decisionPoints?: string[];
  risks?: string[];
}
```

### Operator Card (extends base)

```typescript
interface OperatorCard extends CodexEntity {
  type: 'operator-card';
  checklist: string[];
  commonMistakes: string[];
  scripts?: string[];
}
```

### Glossary Term (extends base)

```typescript
interface GlossaryTerm extends CodexEntity {
  type: 'glossary';
  definition: string;
  relatedTerms: string[];       // slugs
  plainEnglish?: string;
}
```

---

## Relationship Layer

### Graph Builder

Implement `lib/graph-builder.ts` that consumes the normalized course entities and produces a graph structure for the knowledge map:

```typescript
interface GraphNode {
  id: string;
  slug: string;
  label: string;
  type: CodexEntity['type'];
  featured: boolean;
}

interface GraphEdge {
  source: string;   // slug
  target: string;   // slug
  relation: 'related' | 'prerequisite' | 'next-step' | 'pathway-step';
}
```

The graph is derived from `relatedNodes`, `prerequisites`, `nextSteps`, and pathway step arrays in entity metadata.

---

## Experience Layer

### Search

Implement `lib/search-index.ts` using a client-side index (Fuse.js or similar):
- Indexes: title, summary, aliases, searchTerms, tags, plainEnglish
- Groups results by entity type
- Returns pathway suggestions alongside topic results
- No chatbot UI — pure keyword + fuzzy search

### Bookmarks / Recent History

Use `localStorage` for v1:
- Recent history: last 10 visited entity slugs with timestamps
- Bookmarks: saved entity slugs with course context
- Surface on course landing page as "Continue Exploring"

---

## Pages / Features

### 1. Course Landing (`/[course]`)
- Course title + overview
- Search bar (prominent, non-chat)
- Start Exploring CTA
- Featured topic hubs (from `featured: true` in frontmatter)
- Featured case studies
- Featured pathways
- Continue Exploring / recent history (from localStorage)

### 2. Topic Page (`/[course]/topic/[slug]`)
1. Plain-English explanation
2. Why it matters
3. When it is used
4. Prerequisites (linked)
5. Risks / red flags
6. Related concepts (linked)
7. Connected case studies
8. Connected operator quick cards
9. Glossary terms used
10. State-specific notes (if available)
11. Next-step links
12. Breadcrumb trail
13. Back-to-previous-path support
14. Save/bookmark toggle

### 3. Knowledge Map (`/[course]/map`)
- Visual graph using `@xyflow/react`
- Clickable nodes that navigate to entity page
- Zoom and pan
- Highlight current node and its neighbors
- Color-coded by entity type
- Filter toggle by type

### 4. Case Study View (`/[course]/case-study/[slug]`)
- Scenario
- Doctrines/concepts involved (linked topics)
- The play
- Outcome
- Takeaway
- Related topics

### 5. Operator Cards (`/[course]/operator/[slug]`)
- Practical reference card layout
- Checklist
- Common mistakes
- Scripts/forms where applicable

### 6. Glossary (`/[course]/glossary` and `/[course]/glossary/[slug]`)
- Alphabetical index page
- Individual term pages with definition, plain English, related terms

### 7. Pathway View (`/[course]/pathway/[slug]`)
- Entry condition
- Ordered steps (each linking to a topic)
- Decision points at each step
- Likely documents
- Risks
- State sensitivity notes

---

## Search / Discovery

Non-chat discovery experience:
- Exact keyword matching
- Alias and synonym support via `aliases` and `searchTerms` frontmatter
- Plain-language to concept matching via `plainEnglish` field
- Related result suggestions
- Results grouped by entity type
- Recent/popular topics (from localStorage visit history)
- Pathway suggestions when search matches entry conditions
- No chatbot UI whatsoever

---

## Course Config

Each course must include a `course.config.yaml`:

```yaml
slug: fractured-equity
title: Fractured Equity Codex
description: >
  The complete operator's knowledge system for working with
  fractured title, partial interests, and distressed ownership.
productSlug: fractured-equity
version: "1.0"
featured:
  topics:
    - fractured-equity
    - partition-action
    - affidavit-of-heirship
  caseStudies:
    - inherited-property-missing-heir
    - co-owner-wont-sell
  pathways:
    - co-owner-wont-sell
    - inherited-property-with-missing-heirs
```

---

## Initial Content: Fractured Equity

**Source:** Extract from `/apps/codex/course-guides/fractured-equity/MASTER CODEX MANUSCRIPT.docx`. Use the manuscript as the authoritative content source. Convert key sections to markdown with frontmatter.

### Topics (minimum)
- `fractured-equity` — Fractured Equity
- `partial-interest` — Partial Interest
- `partition-action` — Partition Action
- `contribution-suit` — Contribution Suit
- `tax-foreclosure-intervention` — Tax Foreclosure Intervention
- `affidavit-of-heirship` — Affidavit of Heirship
- `missing-heirs` — Missing Heirs
- `quiet-title` — Quiet Title

### Case Studies (minimum 3)
- `inherited-property-missing-heir` — Inherited property with an untraceable heir
- `co-owner-wont-sell` — Uncooperative co-owner blocking a sale
- `tax-lien-partial-interest` — Tax lien against one co-owner's partial interest

### Operator Quick Cards (minimum 3)
- `partition-action-checklist` — Partition Action Operator Checklist
- `heirship-affidavit-checklist` — Affidavit of Heirship Checklist
- `quiet-title-checklist` — Quiet Title Operator Checklist

### Glossary Terms (minimum 10)
- tenancy-in-common
- joint-tenancy
- right-of-survivorship
- partition-in-kind
- partition-by-sale
- intestate-succession
- probate
- chain-of-title
- lis-pendens
- contribution

### Pathways (minimum 3)
- `co-owner-wont-sell` — Co-owner won't sell
- `inherited-property-with-missing-heirs` — Inherited property with missing heirs
- `title-cleanup-before-sale` — Title cleanup before sale

---

## How to Add a New Codex Course

1. Create `/apps/codex/course-guides/<course-slug>/`
2. Add `course.config.yaml` — set `productSlug` to the course slug (must match what gets written to `products[]` in Cosmos when the user purchases)
3. Add `overview.md`
4. Populate subdirectories: `topics/`, `case-studies/`, `operator-cards/`, `glossary/`, `pathways/`, `documents/`, `state-notes/`
5. In `apps/api`, add a Stripe Product for the new course and configure the webhook to write `<course-slug>` to `products[]` on purchase
6. The content loader, routes, graph, search index, and entitlement check are all derived automatically from the content files and `productSlug` — no other code changes required

---

## Progress Tracking

Keep a `PROGRESS.md` inside `apps/codex/` tracking:
- Architecture decisions made
- Current status
- Tasks completed
- Tasks remaining
- Open questions / follow-up integration items

---

## Implementation Approach

Start by inspecting the existing ARI codebase before writing any code. Specifically:

1. Read `apps/web/app/(auth)/auth.ts` — understand the NextAuth setup to mirror it
2. Read `apps/web/app/globals.css` — extract the full CSS variable block to copy
3. Read `apps/web/components/ui/` — identify which shadcn/ui components to copy
4. Read `apps/web/app/api/billing/` — understand how tier/billing status is fetched
5. Read `apps/web/lib/api-proxy.ts` — understand the proxy pattern for backend calls

Then produce a short implementation plan (added to `PROGRESS.md`) covering:
1. How auth/session will be wired up
2. How entitlement checks will work (v1 tier mapping)
3. Which theme/design tokens are being copied
4. Which shared components are being copied
5. What new codex-specific modules are being created

Then implement the codex app according to this spec.

---

## Constraints

- Do not create a separate standalone login system — mirror NextAuth from `apps/web`
- Do not invent a disconnected visual theme — copy ARI tokens
- Do not hardcode only one course into the route structure
- Do not hardcode all content into a single JSON blob
- Do not build a chatbot interface
- Do not use Vercel for deployment — Azure App Service only
- Do not use Tailwind v3 — use v4 with inline CSS variables
- Do not use `react-flow` — use `@xyflow/react`
- Do not expose course content to users who fail the entitlement check
- Do not gate codex access by ARI tier (`elite`, `pro`, `lite`) — tier is for ARI AI features, not courses
- Do not let a purchase of course A grant access to course B — entitlement is per-`productSlug`
