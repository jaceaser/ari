import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Markdown from 'react-native-markdown-display';

type Props = {
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
};

export function ChatBubble({ role, text, streaming }: Props) {
  const isUser = role === 'user';

  if (isUser) {
    return (
      <View style={[styles.row, styles.userRow]}>
        <View style={styles.userBubble}>
          <Text style={styles.userText}>{text}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.row, styles.assistantRow]}>
      <View style={styles.assistantBubble}>
        <Markdown style={markdownStyles}>{text || (streaming ? '▍' : '')}</Markdown>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    paddingHorizontal: 16,
    paddingVertical: 4,
    flexDirection: 'row',
  },
  userRow: {
    justifyContent: 'flex-end',
  },
  assistantRow: {
    justifyContent: 'flex-start',
  },
  userBubble: {
    backgroundColor: '#1a56db',
    borderRadius: 18,
    borderBottomRightRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
    maxWidth: '80%',
  },
  userText: {
    color: '#fff',
    fontSize: 15,
    lineHeight: 21,
  },
  assistantBubble: {
    maxWidth: '92%',
  },
});

const markdownStyles = {
  body: {
    fontSize: 15,
    lineHeight: 22,
    color: '#111827',
  },
  strong: {
    fontWeight: '700' as const,
  },
  bullet_list: {
    marginTop: 4,
    marginBottom: 4,
  },
  ordered_list: {
    marginTop: 4,
    marginBottom: 4,
  },
  code_inline: {
    backgroundColor: '#f3f4f6',
    borderRadius: 4,
    paddingHorizontal: 4,
    fontFamily: 'monospace',
    fontSize: 13,
  },
  fence: {
    backgroundColor: '#f3f4f6',
    borderRadius: 8,
    padding: 12,
    marginVertical: 6,
  },
  link: {
    color: '#1a56db',
  },
  heading1: { fontSize: 20, fontWeight: '700' as const, marginVertical: 8 },
  heading2: { fontSize: 17, fontWeight: '700' as const, marginVertical: 6 },
  heading3: { fontSize: 15, fontWeight: '600' as const, marginVertical: 4 },
};
