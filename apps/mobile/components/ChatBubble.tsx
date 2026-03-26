import React, { useMemo } from 'react';
import { View, Text, TouchableOpacity, Image, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Markdown from 'react-native-markdown-display';
import { useTranslation } from 'react-i18next';
import { useColors } from '../lib/theme-context';
import { ColorTokens } from '../lib/colors';
import { TypingIndicator } from './TypingIndicator';

type Props = {
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  images?: string[];
  docs?: string[];
};

export function ChatBubble({ role, text, streaming, isError, onRetry, images, docs }: Props) {
  const { t } = useTranslation();
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const mdStyles = useMemo(() => makeMarkdownStyles(colors), [colors]);

  if (role === 'user') {
    const hasImages = images && images.length > 0;
    const hasDocs = docs && docs.length > 0;
    return (
      <View style={styles.userRow}>
        <View style={styles.userBubble}>
          {hasImages && (
            <View style={styles.attachImages}>
              {images.map((uri, i) => (
                <Image key={i} source={{ uri }} style={styles.attachImage} />
              ))}
            </View>
          )}
          {hasDocs && (
            <View style={styles.attachDocs}>
              {docs.map((name, i) => (
                <View key={i} style={styles.attachDoc}>
                  <Ionicons name="document-text" size={13} color={colors.primaryForeground} style={{ opacity: 0.8 }} />
                  <Text style={styles.attachDocName} numberOfLines={1}>{name}</Text>
                </View>
              ))}
            </View>
          )}
          {!!text && <Text style={styles.userText}>{text}</Text>}
        </View>
      </View>
    );
  }

  if (isError) {
    return (
      <View style={styles.assistantRow}>
        <View style={[styles.avatar, styles.avatarError]}>
          <Ionicons name="alert" size={14} color={colors.destructive} />
        </View>
        <View style={styles.assistantContent}>
          <View style={styles.errorBubble}>
            <Text style={[styles.errorText, { color: colors.destructive }]}>{text}</Text>
          </View>
          {onRetry && (
            <TouchableOpacity style={styles.retryBtn} onPress={onRetry} activeOpacity={0.7}>
              <Ionicons name="refresh" size={13} color={colors.primary} style={{ marginRight: 4 }} />
              <Text style={[styles.retryText, { color: colors.primary }]}>{t('chat.tryAgain')}</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.assistantRow}>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>A</Text>
      </View>
      <View style={styles.assistantContent}>
        {streaming && !text ? (
          <TypingIndicator />
        ) : (
          <Markdown style={mdStyles}>{text}</Markdown>
        )}
      </View>
    </View>
  );
}

const makeStyles = (c: ColorTokens) => StyleSheet.create({
  userRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingHorizontal: 16,
    paddingVertical: 4,
  },
  userBubble: {
    backgroundColor: c.primary,
    borderRadius: 20,
    borderBottomRightRadius: 5,
    paddingHorizontal: 12,
    paddingVertical: 10,
    maxWidth: '78%',
    gap: 6,
  },
  userText: {
    color: c.primaryForeground,
    fontSize: 15,
    lineHeight: 22,
    fontWeight: '500',
    paddingHorizontal: 4,
  },
  attachImages: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
  },
  attachImage: {
    width: 120,
    height: 120,
    borderRadius: 12,
    backgroundColor: `${c.primaryForeground}22`,
  },
  attachDocs: {
    gap: 4,
  },
  attachDoc: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: `${c.primaryForeground}22`,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  attachDocName: {
    fontSize: 12,
    color: c.primaryForeground,
    opacity: 0.9,
    flex: 1,
  },
  assistantRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 10,
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: c.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
    flexShrink: 0,
  },
  avatarError: {
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: c.destructive,
  },
  avatarText: {
    color: c.primaryForeground,
    fontSize: 13,
    fontWeight: '800',
  },
  assistantContent: { flex: 1 },
  errorBubble: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: c.destructive,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: `${c.destructive}14`,
  },
  errorText: {
    fontSize: 14,
    lineHeight: 20,
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    marginTop: 8,
    paddingVertical: 4,
  },
  retryText: {
    fontSize: 13,
    fontWeight: '600',
  },
});

const makeMarkdownStyles = (c: ColorTokens) => ({
  body: { fontSize: 15, lineHeight: 23, color: c.foreground },
  paragraph: { marginTop: 0, marginBottom: 8 },
  strong: { fontWeight: '700' as const },
  em: { fontStyle: 'italic' as const },
  bullet_list: { marginTop: 4, marginBottom: 8 },
  ordered_list: { marginTop: 4, marginBottom: 8 },
  list_item: { marginBottom: 2 },
  code_inline: {
    backgroundColor: c.muted,
    borderRadius: 5,
    paddingHorizontal: 5,
    paddingVertical: 1,
    fontFamily: 'monospace',
    fontSize: 13,
    color: c.foreground,
  },
  fence: {
    backgroundColor: c.muted,
    borderRadius: 10,
    padding: 14,
    marginVertical: 8,
    fontFamily: 'monospace',
    fontSize: 13,
  },
  blockquote: {
    borderLeftWidth: 3,
    borderLeftColor: c.primary,
    paddingLeft: 12,
    marginLeft: 0,
    color: c.mutedForeground,
  },
  link: { color: c.primary, textDecorationLine: 'underline' as const },
  heading1: { fontSize: 20, fontWeight: '700' as const, marginTop: 12, marginBottom: 6, color: c.foreground },
  heading2: { fontSize: 17, fontWeight: '700' as const, marginTop: 10, marginBottom: 4, color: c.foreground },
  heading3: { fontSize: 15, fontWeight: '600' as const, marginTop: 8, marginBottom: 4, color: c.foreground },
  hr: { backgroundColor: c.border, height: 1, marginVertical: 12 },
});
