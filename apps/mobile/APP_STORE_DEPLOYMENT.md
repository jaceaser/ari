# App Store Deployment Guide

## App Details

| Field | Value |
|-------|-------|
| App name | ARI |
| iOS bundle ID | `ai.reilabs.ari` |
| Android package | `ai.reilabs.ari` |
| EAS project ID | `8b1fee66-b7ac-4040-9a9f-30d2ab47a37f` |
| EAS owner | `jaceaser` |

---

## Prerequisites

```bash
npm install -g eas-cli
eas login   # log in as jaceaser
```

Ensure credentials are configured:

```bash
eas credentials --platform ios
eas credentials --platform android
```

---

## Build Production Binaries

```bash
cd apps/mobile

# Build both platforms (queued on EAS servers)
eas build --platform all --profile production

# Or build individually
eas build --platform ios --profile production
eas build --platform android --profile production
```

Builds are queued remotely. Monitor at https://expo.dev/accounts/jaceaser/projects/ari-mobile/builds

---

## Submit to Stores

After the build completes:

```bash
# Submit latest builds to both stores
eas submit --platform ios --latest
eas submit --platform android --latest
```

### iOS — additional requirements
- Apple Developer account must have an active paid membership
- App Store Connect app record must exist for bundle ID `ai.reilabs.ari`
- At least one screenshot per device size (6.7" iPhone required; iPad optional)
- App Store Connect API key configured in EAS (`eas credentials`) **or** provide Apple ID + app-specific password at submission time

### Android — additional requirements
- Google Play Console app record must exist for package `ai.reilabs.ari`
- Service account JSON key configured in EAS (`eas credentials`) **or** upload APK/AAB manually via Play Console
- First release must be uploaded manually via Play Console (subsequent ones can use `eas submit`)

---

## Review Credentials

Provide these in the **Notes for Reviewers** section of both store listings.

### iOS (App Store Connect → Version → App Review Information)

```
Demo account:
  Username: review-ios@reilabs.ai
  Password: (no password — see instructions below)

Login instructions:
  1. Open the app
  2. Tap "Sign In"
  3. Tap "Reviewer access" (small grey link at the bottom of the login screen)
  4. Enter code: ARIOS4W
  5. Tap Continue — you will be signed in automatically

Note: The app uses magic-link authentication. The review code bypasses
the email flow so reviewers can sign in without an inbox.
```

### Android (Google Play Console → Release Notes / Reviewer notes)

```
Demo account:
  Username: review-android@reilabs.ai
  Password: (no password — see instructions below)

Login instructions:
  1. Open the app
  2. Tap "Sign In"
  3. Tap "Reviewer access" (small grey link at the bottom of the login screen)
  4. Enter code: ARAND4W
  5. Tap Continue — you will be signed in automatically
```

**Review codes expire: April 24, 2026.** To rotate: update `REVIEW_CODE_IOS` and
`REVIEW_CODE_ANDROID` in the `reilabs-ari-api` App Service config, then rebuild and
redeploy the API image.

---

## Version / Build Number

`eas.json` uses `"autoIncrement": true` on the production profile, so EAS manages
build numbers automatically. No manual changes to `app.json` needed for build number bumps.

To bump the **user-visible version** (e.g., 1.0.0 → 1.1.0), edit `version` in `app.json`
before building.

---

## Environment

The production build uses `EXPO_PUBLIC_API_URL=https://api.reilabs.ai` (set in `eas.json`).

Deep links use the `ari://` custom scheme and `https://reilabs.ai/auth/verify` universal link.
Make sure the `.well-known/apple-app-site-association` and `assetlinks.json` files are
served at `https://reilabs.ai` for universal/app links to work.

---

## Checklist Before Submitting

- [ ] Production EAS build completed successfully
- [ ] Screenshots uploaded for all required device sizes
- [ ] App description, keywords, and category filled in
- [ ] Privacy policy URL set to `https://reilabs.ai/privacy-policy`
- [ ] Review credentials in reviewer notes (see above)
- [ ] Age rating completed
- [ ] Export compliance answered (app does NOT use non-exempt encryption — `ITSAppUsesNonExemptEncryption: false` set in `app.json`)
- [ ] iOS: App Review contact email/phone filled in
- [ ] Android: Content rating questionnaire completed
