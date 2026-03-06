import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Markdown from 'react-native-markdown-display';
import { colors } from '../lib/colors';

type Props = {
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
};

export function ChatBubble({ role, text, streaming }: Props) {
  if (role === 'user') {
    return (
      <View style={styles.userRow}>
        <View style={styles.userBubble}>
          <Text style={styles.userText}>{text}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.assistantRow}>
      {/* ARI avatar */}
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>A</Text>
      </View>
      <View style={styles.assistantContent}>
        <Markdown style={markdownStyles}>
          {text || (streaming ? '▍' : '')}
        </Markdown>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // User message — right-aligned gold pill
  userRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingHorizontal: 16,
    paddingVertical: 4,
  },
  userBubble: {
    backgroundColor: colors.primary,
    borderRadius: 20,
    borderBottomRightRadius: 5,
    paddingHorizontal: 16,
    paddingVertical: 10,
    maxWidth: '78%',
  },
  userText: {
    color: colors.primaryForeground,
    fontSize: 15,
    lineHeight: 22,
    fontWeight: '500',
  },

  // Assistant message — avatar + plain text, no bubble
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
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
    flexShrink: 0,
  },
  avatarText: {
    color: colors.primaryForeground,
    fontSize: 13,
    fontWeight: '800',
  },
  assistantContent: {
    flex: 1,
  },
});

const markdownStyles = {
  body: {
    fontSize: 15,
    lineHeight: 23,
    color: colors.foreground,
  },
  paragraph: {
    marginTop: 0,
    marginBottom: 8,
  },
  strong: { fontWeight: '700' as const },
  em: { fontStyle: 'italic' as const },
  bullet_list: { marginTop: 4, marginBottom: 8 },
  ordered_list: { marginTop: 4, marginBottom: 8 },
  list_item: { marginBottom: 2 },
  code_inline: {
    backgroundColor: colors.muted,
    borderRadius: 5,
    paddingHorizontal: 5,
    paddingVertical: 1,
    fontFamily: 'monospace',
    fontSize: 13,
    color: colors.foreground,
  },
  fence: {
    backgroundColor: colors.muted,
    borderRadius: 10,
    padding: 14,
    marginVertical: 8,
    fontFamily: 'monospace',
    fontSize: 13,
  },
  blockquote: {
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    paddingLeft: 12,
    marginLeft: 0,
    color: colors.mutedForeground,
  },
  link: { color: colors.primary, textDecorationLine: 'underline' as const },
  heading1: { fontSize: 20, fontWeight: '700' as const, marginTop: 12, marginBottom: 6, color: colors.foreground },
  heading2: { fontSize: 17, fontWeight: '700' as const, marginTop: 10, marginBottom: 4, color: colors.foreground },
  heading3: { fontSize: 15, fontWeight: '600' as const, marginTop: 8, marginBottom: 4, color: colors.foreground },
  hr: { backgroundColor: colors.border, height: 1, marginVertical: 12 },
};
