import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
  Text,
} from 'react-native';
import * as Crypto from 'expo-crypto';
import { ChatBubble } from '../../components/ChatBubble';
import { ChatInput } from '../../components/ChatInput';
import { useChatStream } from '../../hooks/useChatStream';
import { createSession } from '../../lib/api';
import { colors } from '../../lib/colors';

export default function NewChatScreen() {
  const [sessionId] = useState(() => Crypto.randomUUID());
  const sessionCreatedRef = useRef(false);

  const { messages, streaming, error, sendMessage } = useChatStream(sessionId);
  const listRef = useRef<FlatList>(null);

  useEffect(() => {
    if (messages.length > 0) {
      listRef.current?.scrollToEnd({ animated: true });
    }
  }, [messages]);

  const handleSend = async (text: string) => {
    if (!sessionCreatedRef.current) {
      sessionCreatedRef.current = true;
      try {
        await createSession(sessionId);
      } catch {
        sessionCreatedRef.current = false;
        return;
      }
    }
    sendMessage(text);
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>ARI</Text>
      </View>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={0}
      >
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => m.id}
          renderItem={({ item, index }) => (
            <ChatBubble
              role={item.role}
              text={item.text}
              streaming={
                streaming &&
                index === messages.length - 1 &&
                item.role === 'assistant'
              }
            />
          )}
          contentContainerStyle={styles.list}
          ListEmptyComponent={<EmptyState />}
        />
        {error && <Text style={styles.errorText}>{error}</Text>}
        <ChatInput onSend={handleSend} disabled={streaming} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function EmptyState() {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyLogo}>ARI</Text>
      <Text style={styles.emptyTitle}>Real Estate Intelligence</Text>
      <Text style={styles.emptyHint}>
        Ask for leads, comps, buyers, contracts, or strategy.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  header: {
    height: 52,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: colors.primary,
    letterSpacing: 1,
  },
  list: { paddingTop: 16, paddingBottom: 8 },
  errorText: {
    color: colors.destructive,
    fontSize: 13,
    textAlign: 'center',
    paddingHorizontal: 16,
    paddingBottom: 4,
  },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 120,
  },
  emptyLogo: {
    fontSize: 40,
    fontWeight: '800',
    color: colors.primary,
    letterSpacing: 2,
    marginBottom: 8,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.foreground,
    marginBottom: 8,
  },
  emptyHint: {
    fontSize: 14,
    color: colors.mutedForeground,
    textAlign: 'center',
    paddingHorizontal: 40,
  },
});
