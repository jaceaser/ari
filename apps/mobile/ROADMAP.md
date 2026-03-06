# ARI Mobile App — Roadmap

## Phase 1 — Foundation ✅
- [x] Expo 52 project setup (expo-router, NativeWind, TanStack Query)
- [x] Magic link auth with `ari://` deep link scheme
- [x] JWT storage via `expo-secure-store`
- [x] SSE streaming chat (fetch + ReadableStream)
- [x] New chat screen with lazy session creation
- [x] Existing chat screen (load history + continue)
- [x] Session history list
- [x] Account & billing settings (Stripe portal)
- [x] API deployed with `redirect_uri` deep link support

## Phase 2 — UI Polish ✅
- [x] ARI gold color palette from web `globals.css`
- [x] ChatGPT-style message layout
  - User: gold pill bubble (right)
  - Assistant: gold avatar "A" + plain text (no bubble)
- [x] Floating rounded input bar with shadow
- [x] Home screen with suggestion chips
- [x] ChatGPT-style sidebar navigation (no bottom tabs)
  - Hamburger (≡) | title | compose (✏️) header
  - Slide-in sidebar with spring animation
  - Session history grouped: Today / Yesterday / 7 days / 30 days
  - Settings footer link
- [x] Session history `SectionList` with time grouping
- [x] Settings profile card with tier badge

## Phase 3 — Quality & Reliability 🔄 (In Progress)
- [x] Auto-generate session title from first user message (backend)
- [x] Sidebar refreshes when opened + after first message sent
- [ ] **Deep link auth** — Universal Links (iOS) / App Links (Android)
      so magic link email opens the app directly
- [ ] Typing indicator — animated dots while waiting for first token
- [ ] Error states — network error banner, retry button
- [ ] Offline detection

## Phase 4 — App Store Distribution
- [ ] Real app icon (ARI logo) + splash screen
- [ ] EAS account setup (`eas login`, `eas build:configure`)
- [ ] Development build on device (replaces Expo Go)
- [ ] TestFlight (iOS internal testing)
- [ ] Google Play internal track (Android)
- [ ] App Store / Play Store submission

## Phase 5 — Native Features
- [ ] Push notifications (new lead alerts, billing reminders)
- [ ] Haptic feedback on send / receive
- [ ] File/image attachment (camera roll → upload → attach to message)
- [ ] Share sheet integration (share ARI responses)
- [ ] Biometric lock (Face ID / Touch ID for app re-open)
- [ ] Background session sync

## Phase 6 — Power Features
- [ ] Voice input (speech-to-text for queries)
- [ ] Pinned / favorite sessions
- [ ] Search across session history
- [ ] Export chat as PDF
- [ ] Lead run history screen (view past lead searches)
- [ ] Offline message queue (send when connection restored)

---

## Running Locally

```bash
cd apps/mobile
npx expo start        # Expo Go (quick dev)
npx expo run:ios      # Native build on simulator
```

`.env.local` → `http://localhost:8000` (local API)
`.env` → `https://api.reilabs.ai` (production)

## Building for Device

```bash
eas login
eas build:configure
eas build --platform ios --profile development
```
