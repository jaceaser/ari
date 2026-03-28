import React, { useMemo } from 'react';
import { ActionSheetIOS, Alert, Platform, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import i18n from '../lib/i18n';
import { Attachment } from '../lib/api';
import { useColors } from '../lib/theme-context';
import { ColorTokens } from '../lib/colors';

type Props = {
  onAttach: (attachment: Attachment) => void;
  disabled?: boolean;
};

async function pickFromCamera(onAttach: (a: Attachment) => void) {
  const { status } = await ImagePicker.requestCameraPermissionsAsync();
  if (status !== 'granted') {
    Alert.alert(i18n.t('attachment.permissionTitle'), i18n.t('attachment.cameraPermission'));
    return;
  }
  const result = await ImagePicker.launchCameraAsync({
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 0.8,
    allowsEditing: false,
  });
  if (!result.canceled && result.assets[0]) {
    const asset = result.assets[0];
    onAttach({
      uri: asset.uri,
      mimeType: asset.mimeType ?? 'image/jpeg',
      filename: asset.fileName ?? `photo-${Date.now()}.jpg`,
      isImage: true,
    });
  }
}

async function pickFromLibrary(onAttach: (a: Attachment) => void) {
  // Android Photo Picker (PickVisualMedia) requires no permissions.
  // iOS uses PHPickerViewController which also requires no permission.
  // Do not call requestMediaLibraryPermissionsAsync() — it triggers
  // READ_MEDIA_IMAGES which violates Google Play policy.
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ImagePicker.MediaTypeOptions.Images,
    quality: 0.8,
    allowsMultipleSelection: true,
    selectionLimit: 5,
  });
  if (!result.canceled) {
    result.assets.forEach((asset) => {
      onAttach({
        uri: asset.uri,
        mimeType: asset.mimeType ?? 'image/jpeg',
        filename: asset.fileName ?? `image-${Date.now()}.jpg`,
        isImage: true,
      });
    });
  }
}

async function pickDocument(onAttach: (a: Attachment) => void) {
  const result = await DocumentPicker.getDocumentAsync({
    type: ['application/pdf', 'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    copyToCacheDirectory: true,
  });
  if (!result.canceled && result.assets[0]) {
    const asset = result.assets[0];
    onAttach({
      uri: asset.uri,
      mimeType: asset.mimeType ?? 'application/octet-stream',
      filename: asset.name,
      isImage: false,
    });
  }
}

export function AttachmentButton({ onAttach, disabled }: Props) {
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const handlePress = () => {
    if (disabled) return;

    if (Platform.OS === 'ios') {
      ActionSheetIOS.showActionSheetWithOptions(
        {
          options: [i18n.t('attachment.cancel'), i18n.t('attachment.takePhoto'), i18n.t('attachment.photoLibrary'), i18n.t('attachment.document')],
          cancelButtonIndex: 0,
        },
        (index) => {
          if (index === 1) pickFromCamera(onAttach);
          else if (index === 2) pickFromLibrary(onAttach);
          else if (index === 3) pickDocument(onAttach);
        },
      );
    } else {
      Alert.alert(i18n.t('attachment.actionSheetTitle'), i18n.t('attachment.actionSheetSubtitle'), [
        { text: i18n.t('attachment.cancel'), style: 'cancel' },
        { text: i18n.t('attachment.camera'), onPress: () => pickFromCamera(onAttach) },
        { text: i18n.t('attachment.photoLibrary'), onPress: () => pickFromLibrary(onAttach) },
        { text: i18n.t('attachment.document'), onPress: () => pickDocument(onAttach) },
      ]);
    }
  };

  return (
    <TouchableOpacity
      onPress={handlePress}
      disabled={disabled}
      style={styles.btn}
      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
    >
      <Ionicons
        name="attach"
        size={22}
        color={disabled ? colors.border : colors.mutedForeground}
        style={styles.icon}
      />
    </TouchableOpacity>
  );
}

const makeStyles = (c: ColorTokens) => StyleSheet.create({
  btn: { width: 34, height: 34, justifyContent: 'center', alignItems: 'center', marginBottom: 1 },
  icon: { transform: [{ rotate: '45deg' }] },
});
