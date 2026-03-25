import React, { useMemo, useState } from 'react';
import {
  View,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Keyboard,
  ScrollView,
  Image,
  Text,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Attachment } from '../lib/api';
import { AttachmentButton } from './AttachmentButton';
import { useColors } from '../lib/theme-context';
import { ColorTokens } from '../lib/colors';

type Props = {
  onSend: (text: string, attachments: Attachment[]) => void;
  onStop?: () => void;
  disabled?: boolean;
  streaming?: boolean;
};

export function ChatInput({ onSend, onStop, disabled, streaming }: Props) {
  const [text, setText] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const colors = useColors();
  const insets = useSafeAreaInsets();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const canSend = (!!text.trim() || attachments.length > 0) && !disabled && !streaming;

  const handleSend = () => {
    const trimmed = text.trim();
    if ((!trimmed && attachments.length === 0) || disabled) return;
    onSend(trimmed, attachments);
    setText('');
    setAttachments([]);
    Keyboard.dismiss();
  };

  const handleAttach = (attachment: Attachment) => {
    setAttachments((prev) => [...prev, attachment]);
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <View style={[styles.wrapper, { paddingBottom: Math.max(4, insets.bottom) }]}>
      {attachments.length > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.thumbRow}
          contentContainerStyle={styles.thumbContent}
        >
          {attachments.map((a, i) => (
            <View key={i} style={styles.thumb}>
              {a.isImage ? (
                <Image source={{ uri: a.uri }} style={styles.thumbImage} />
              ) : (
                <View style={styles.thumbDoc}>
                  <Ionicons name="document-text-outline" size={20} color={colors.primary} />
                  <Text style={styles.thumbDocName} numberOfLines={1}>{a.filename}</Text>
                </View>
              )}
              <TouchableOpacity
                style={styles.thumbRemove}
                onPress={() => removeAttachment(i)}
                hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
              >
                <Ionicons name="close-circle" size={16} color={colors.mutedForeground} />
              </TouchableOpacity>
            </View>
          ))}
        </ScrollView>
      )}

      <View style={styles.container}>
        <AttachmentButton onAttach={handleAttach} disabled={disabled} />
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder="Message ARI"
          placeholderTextColor={colors.mutedForeground}
          multiline
          maxLength={4000}
          editable={!disabled}
          returnKeyType="default"
        />
        {streaming ? (
          <TouchableOpacity
            style={[styles.sendBtn, styles.stopBtnActive]}
            onPress={onStop}
            hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
          >
            <View style={styles.stopIcon} />
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={[styles.sendBtn, canSend && styles.sendBtnActive]}
            onPress={handleSend}
            disabled={!canSend}
            hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
          >
            <Ionicons
              name="arrow-up"
              size={18}
              color={canSend ? colors.primaryForeground : colors.mutedForeground}
            />
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const makeStyles = (c: ColorTokens) => StyleSheet.create({
  wrapper: {
    paddingHorizontal: 12,
    paddingTop: 8,
    backgroundColor: c.background,
  },
  thumbRow: { marginBottom: 8 },
  thumbContent: { gap: 8, paddingHorizontal: 4 },
  thumb: { position: 'relative' },
  thumbImage: { width: 60, height: 60, borderRadius: 8, backgroundColor: c.muted },
  thumbDoc: {
    width: 100,
    height: 60,
    borderRadius: 8,
    backgroundColor: c.muted,
    borderWidth: 1,
    borderColor: c.border,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
    gap: 4,
  },
  thumbDocName: { fontSize: 10, color: c.foreground, textAlign: 'center' },
  thumbRemove: {
    position: 'absolute',
    top: -4,
    right: -4,
    backgroundColor: c.background,
    borderRadius: 8,
  },
  container: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: c.muted,
    borderRadius: 26,
    borderWidth: 1,
    borderColor: c.border,
    paddingLeft: 8,
    paddingRight: 6,
    paddingVertical: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  input: {
    flex: 1,
    fontSize: 15,
    lineHeight: 21,
    color: c.foreground,
    maxHeight: 130,
    paddingVertical: 4,
    marginLeft: 4,
    marginRight: 4,
  },
  sendBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: c.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 1,
  },
  sendBtnActive: {
    backgroundColor: c.primary,
  },
  stopBtnActive: {
    backgroundColor: c.foreground,
  },
  stopIcon: {
    width: 12,
    height: 12,
    borderRadius: 2,
    backgroundColor: c.background,
  },
});
