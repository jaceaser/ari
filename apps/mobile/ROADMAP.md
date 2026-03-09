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

## Phase 3 — Quality & Reliability ✅
- [x] Auto-generate session title from first user message (backend)
- [x] Sidebar refreshes when opened + after first message sent
- [x] **Deep link auth** — Universal Links (iOS) / App Links (Android)
      so magic link email opens the app directly
  - `ari://verify?token=XXX` custom scheme (works in dev / Expo Go)
  - `https://reilabs.ai/auth/verify?token=XXX` Universal / App Link
  - `apple-app-site-association` + `assetlinks.json` in `apps/web/public/.well-known/`
  - Root layout handles cold-start + foreground deep links; no auth-redirect race
- [x] Image & document upload (camera, photo library, PDF/Word files)
  - Multi-image selection (up to 5 photos at once)
  - Images shown inline in user message bubble
  - Document filenames shown in user message bubble
- [x] Message history loads when reopening a chat
- [x] Dark mode (follows system preference, matches web app dark tokens)
- [x] Typing indicator — animated bouncing dots while waiting for first token
- [x] Error states — inline error bubble with friendly message + retry button
  - Network errors: "Couldn't connect. Check your internet connection."
  - Auth errors: "Session expired. Please sign in again."
  - Rate limit errors: "Too many requests. Please wait."
  - Server errors: "Something went wrong on our end."
- [x] Scroll-to-bottom floating button (shows when scrolled up in long chats)
- [x] History screen error state with retry button
- [x] Offline detection — animated red banner + disabled input when no internet

## Phase 4 — App Store Distribution
- [x] Real app icon (ARI logo) + splash screen
- [ ] EAS account setup (`eas login`, `eas build:configure`)
- [ ] Development build on device (replaces Expo Go)
- [ ] TestFlight (iOS internal testing)
- [ ] Google Play internal track (Android)
- [ ] App Store / Play Store submission

## Phase 5 — Native Features
- [ ] Push notifications (new lead alerts, billing reminders)
- [ ] Haptic feedback on send / receive
- [x] File/image attachment (camera roll → upload → attach to message)
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

## Immediate Next Steps

### 1. Fix Universal Link placeholder (5 min)
File: `apps/web/public/.well-known/apple-app-site-association`

Replace `XXXXXXXXXX` with your Apple Team ID:
- Find it at: https://developer.apple.com → Account → Membership → Team ID
- Example: `A1B2C3D4E5.ai.reilabs.ari`

### 2. Fix Android App Link placeholder (before Play Store)
File: `apps/web/public/.well-known/assetlinks.json`

Replace `PLACEHOLDER_REPLACE_WITH_RELEASE_KEYSTORE_SHA256` with your release keystore SHA-256.
- Run: `keytool -list -v -keystore release.keystore` to get the fingerprint
- Only needed for production builds (dev builds can use debug keystore)

### 3. Deploy web app (so `.well-known` files go live)
```bash
# From apps/web — trigger a redeploy so AASA + assetlinks.json are served
az acr build -r ariprodacr -t ari-web:latest --build-arg NEXT_PUBLIC_API_URL=https://reilabs-ari-api.azurewebsites.net --file Dockerfile .
az webapp restart -g rg-ari-prod -n ari-web
```
Verify: `curl https://reilabs.ai/.well-known/apple-app-site-association`

### 4. EAS setup + dev build on device
```bash
cd apps/mobile
eas login                          # log in with Expo account (jaceaser)
eas build:configure                # generates eas.json
eas build --platform ios --profile development   # ~10 min cloud build
# Install the resulting .ipa on your iPhone via the Expo Go QR or direct download
```

### 5. Test deep links end-to-end on device
Once the dev build is installed and AASA is live:
1. Send a magic link email to yourself
2. Tap the link in the email → should open ARI app directly to verify screen
3. Also test custom scheme: `ari://verify?token=abc123` via Notes → tap link

### 6. TestFlight (iOS internal)
```bash
eas build --platform ios --profile preview   # ad-hoc / internal distribution
# or
eas submit --platform ios                    # submit to App Store Connect
```
Requires: Apple Developer account ($99/yr), app registered in App Store Connect

### 7. Google Play internal track (Android)
```bash
eas build --platform android --profile preview
eas submit --platform android
```
Requires: Google Play Console account ($25 one-time), app created in Play Console

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
