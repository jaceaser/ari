import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
  Text,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import * as Crypto from 'expo-crypto';
import { ChatBubble } from '../../components/ChatBubble';
import { ChatInput } from '../../components/ChatInput';
import { useChatStream } from '../../hooks/useChatStream';
import { createSession } from '../../lib/api';
import { colors } from '../../lib/colors';

const SUGGESTIONS = [
  'Get me a list of tired landlords in Dallas, TX',
  'Find cash buyers for a 3/2 in Houston, TX',
  'Pull comps for 123 Main St, Atlanta, GA',
  'Draft a purchase agreement for a wholesale deal',
];

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

  const showEmpty = messages.length === 0;

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
        {showEmpty ? (
          <ScrollView
            contentContainerStyle={styles.emptyContainer}
            keyboardShouldPersistTaps="handled"
          >
            <View style={styles.emptyTop}>
              <View style={styles.logoCircle}>
                <Text style={styles.logoText}>A</Text>
              </View>
              <Text style={styles.greeting}>How can I help you?</Text>
              <Text style={styles.greetingSub}>Real estate intelligence at your fingertips</Text>
            </View>

            <View style={styles.suggestionsGrid}>
              {SUGGESTIONS.map((s) => (
                <TouchableOpacity
                  key={s}
                  style={styles.chip}
                  onPress={() => handleSend(s)}
                  activeOpacity={0.7}
                >
                  <Text style={styles.chipText}>{s}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </ScrollView>
        ) : (
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
          />
        )}

        {error ? <Text style={styles.errorText}>{error}</Text> : null}
        <ChatInput onSend={handleSend} disabled={streaming} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },

  header: {
    height: 52,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '800',
    color: colors.foreground,
    letterSpacing: 2,
  },

  // Empty / home state
  emptyContainer: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingTop: 48,
    paddingBottom: 16,
  },
  emptyTop: {
    alignItems: 'center',
    marginBottom: 40,
  },
  logoCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 6,
  },
  logoText: {
    fontSize: 28,
    fontWeight: '800',
    color: colors.primaryForeground,
  },
  greeting: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.foreground,
    marginBottom: 6,
    textAlign: 'center',
  },
  greetingSub: {
    fontSize: 14,
    color: colors.mutedForeground,
    textAlign: 'center',
  },

  suggestionsGrid: {
    gap: 10,
  },
  chip: {
    backgroundColor: colors.muted,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  chipText: {
    fontSize: 14,
    color: colors.foreground,
    lineHeight: 20,
  },

  // Chat
  list: { paddingTop: 12, paddingBottom: 8 },
  errorText: {
    color: colors.destructive,
    fontSize: 13,
    textAlign: 'center',
    paddingHorizontal: 16,
    paddingBottom: 4,
  },
});
