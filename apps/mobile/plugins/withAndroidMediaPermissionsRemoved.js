/**
 * Expo config plugin that removes broad media storage permissions from the
 * final merged Android manifest.
 *
 * expo-image-picker's library AndroidManifest.xml unconditionally declares
 * READ_MEDIA_IMAGES, READ_MEDIA_VIDEO, READ_EXTERNAL_STORAGE, and
 * WRITE_EXTERNAL_STORAGE. Gradle's manifest merger combines all library
 * manifests at build time, so simply removing them from the app manifest
 * is not enough — the library re-adds them.
 *
 * The correct fix is to add <uses-permission tools:node="remove" /> entries,
 * which instruct the manifest merger to explicitly DROP those permissions even
 * if any library manifest declares them.
 */
const { withAndroidManifest } = require('@expo/config-plugins');

const BLOCKED_PERMISSIONS = [
  'android.permission.READ_MEDIA_IMAGES',
  'android.permission.READ_MEDIA_VIDEO',
  'android.permission.READ_EXTERNAL_STORAGE',
  'android.permission.WRITE_EXTERNAL_STORAGE',
];

module.exports = function withAndroidMediaPermissionsRemoved(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;

    // Ensure the tools namespace is declared on the root <manifest> element.
    manifest.$['xmlns:tools'] = 'http://schemas.android.com/tools';

    // Remove any plain existing entries for these permissions (no-op if absent).
    const existing = manifest['uses-permission'] ?? [];
    const filtered = existing.filter(
      (p) => !BLOCKED_PERMISSIONS.includes(p.$?.['android:name'])
    );

    // Add tools:node="remove" entries — these override library manifest entries
    // during Gradle's manifest merge and ensure the permissions are absent from
    // the final APK/AAB regardless of what any library manifest declares.
    const removals = BLOCKED_PERMISSIONS.map((name) => ({
      $: { 'android:name': name, 'tools:node': 'remove' },
    }));

    manifest['uses-permission'] = [...filtered, ...removals];
    return config;
  });
};
