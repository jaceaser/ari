/**
 * Expo config plugin that blocks broad media/storage permissions from
 * appearing in the final Android build.
 *
 * Permission sources:
 *   1. expo-image-picker library AndroidManifest.xml declares READ_MEDIA_IMAGES,
 *      READ_MEDIA_VIDEO, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE.
 *   2. expo-file-system JS plugin calls withPermissions([READ_EXTERNAL_STORAGE,
 *      WRITE_EXTERNAL_STORAGE]) which adds them to the app manifest.
 *   3. @expo/config-plugins base manifest template includes READ_EXTERNAL_STORAGE
 *      and WRITE_EXTERNAL_STORAGE as "optional" permissions.
 *
 * Fix strategy:
 *   A. withDangerousMod: directly remove declarations from library AndroidManifest.xml
 *      files in node_modules before Gradle runs. This eliminates the source-level
 *      declarations that Gradle would merge in.
 *   B. withBlockedPermissions: registers a withAndroidManifest mod (via Expo's official
 *      API) that:
 *        - Adds tools:node="remove" entries to the app manifest for each blocked permission
 *        - Sets isPermissionAlreadyRequested=true so that expo-file-system's
 *          withPermissions() mod (which runs AFTER ours in the chain) skips adding
 *          plain entries for these permissions
 *
 * This combination is belt-and-suspenders: library manifests are clean at the XML
 * level, AND the app manifest carries tools:node="remove" to override any remaining
 * declarations from other library manifests not yet patched.
 *
 * CAMERA, INTERNET, RECORD_AUDIO are NOT blocked.
 */
const { withDangerousMod, AndroidConfig } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

const ALL_BLOCKED = [
  'android.permission.READ_MEDIA_IMAGES',
  'android.permission.READ_MEDIA_VIDEO',
  'android.permission.READ_EXTERNAL_STORAGE',
  'android.permission.WRITE_EXTERNAL_STORAGE',
];

const LIBRARY_PATCHES = [
  {
    library: 'expo-image-picker',
    manifestRelPath: path.join('android', 'src', 'main', 'AndroidManifest.xml'),
    permissions: ALL_BLOCKED,
  },
  {
    library: 'expo-file-system',
    manifestRelPath: path.join('android', 'src', 'main', 'AndroidManifest.xml'),
    permissions: [
      'android.permission.READ_EXTERNAL_STORAGE',
      'android.permission.WRITE_EXTERNAL_STORAGE',
    ],
  },
];

function patchLibraryManifest(manifestPath, permissions) {
  if (!fs.existsSync(manifestPath)) return false;
  let content = fs.readFileSync(manifestPath, 'utf8');
  const original = content;
  for (const perm of permissions) {
    content = content.replace(
      new RegExp(`[ \\t]*<uses-permission[^>]*android:name="${perm}"[^/]*/>[\\r\\n]?`, 'g'),
      '',
    );
  }
  if (content !== original) {
    fs.writeFileSync(manifestPath, content, 'utf8');
    return true;
  }
  return false;
}

module.exports = function withAndroidMediaPermissionsRemoved(config) {
  // A. Patch library AndroidManifest.xml files in node_modules.
  //    withDangerousMod runs before withAndroidManifest mods, so these patches
  //    persist into Gradle's library manifest merge.
  config = withDangerousMod(config, [
    'android',
    (config) => {
      const projectRoot = config.modRequest.projectRoot;
      for (const { library, manifestRelPath, permissions } of LIBRARY_PATCHES) {
        const mp = path.join(projectRoot, 'node_modules', library, manifestRelPath);
        const patched = patchLibraryManifest(mp, permissions);
        console.log(
          `[withAndroidMediaPermissionsRemoved] ${library}: ${patched ? 'patched' : 'already clean or missing'}`,
        );
      }
      return config;
    },
  ]);

  // B. Block permissions in the app manifest via the official Expo API.
  //    withBlockedPermissions adds tools:node="remove" entries, which:
  //      - Prevents expo-file-system's withPermissions from adding plain entries
  //        (isPermissionAlreadyRequested returns true for tools:node="remove" entries)
  //      - Tells Gradle's manifest merger to remove these permissions even if a
  //        library manifest re-declares them
  config = AndroidConfig.Permissions.withBlockedPermissions(config, ALL_BLOCKED);

  return config;
};
