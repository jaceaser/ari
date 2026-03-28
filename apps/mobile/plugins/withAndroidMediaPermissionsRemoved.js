/**
 * Expo config plugin that removes broad media storage permissions from the
 * merged Android manifest.
 *
 * expo-image-picker unconditionally declares READ_MEDIA_IMAGES,
 * READ_MEDIA_VIDEO, READ_EXTERNAL_STORAGE, and WRITE_EXTERNAL_STORAGE in its
 * own AndroidManifest.xml. These permissions violate Google Play policy for
 * apps that only need one-time/infrequent photo access.
 *
 * launchImageLibraryAsync() uses the Android Photo Picker (PickVisualMedia)
 * which requires no permissions at all, so these declarations serve no purpose.
 */
const { withAndroidManifest } = require('@expo/config-plugins');

const BLOCKED_PERMISSIONS = new Set([
  'android.permission.READ_MEDIA_IMAGES',
  'android.permission.READ_MEDIA_VIDEO',
  'android.permission.READ_EXTERNAL_STORAGE',
  'android.permission.WRITE_EXTERNAL_STORAGE',
]);

module.exports = function withAndroidMediaPermissionsRemoved(config) {
  return withAndroidManifest(config, (config) => {
    const perms = config.modResults.manifest['uses-permission'] ?? [];
    config.modResults.manifest['uses-permission'] = perms.filter(
      (p) => !BLOCKED_PERMISSIONS.has(p.$?.['android:name'])
    );
    return config;
  });
};
