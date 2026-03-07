import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { Ionicons } from '@expo/vector-icons';
import * as Crypto from 'expo-crypto';
import { useQueryClient } from '@tanstack/react-query';
import { ChatBubble } from '../../components/ChatBubble';
import { ChatInput } from '../../components/ChatInput';
import { ChatHeader } from '../../components/ChatHeader';
import { useChatStream } from '../../hooks/useChatStream';
import { useNetworkStatus } from '../../hooks/useNetworkStatus';
import { createSession, Attachment } from '../../lib/api';
import { useColors } from '../../lib/theme-context';
import { ColorTokens } from '../../lib/colors';

const SUGGESTIONS = [
  'Get me a list of tired landlords in Dallas, TX',
  'Find cash buyers for a 3/2 in Houston, TX',
  'Pull comps for 123 Main St, Atlanta, GA',
  'Draft a purchase agreement for a wholesale deal',
];

const AT_BOTTOM_THRESHOLD = 80;

export default function NewChatScreen() {
  const [sessionId] = useState(() => Crypto.randomUUID());
  const sessionCreatedRef = useRef(false);
  const { messages, streaming, sendMessage, retry } = useChatStream(sessionId);
  const { isConnected } = useNetworkStatus();
  const listRef = useRef<FlatList>(null);
  const queryClient = useQueryClient();
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const isAtBottomRef = useRef(true);

  useEffect(() => {
    if (messages.length > 0 && isAtBottomRef.current) {
      listRef.current?.scrollToEnd({ animated: true });
    }
  }, [messages]);

  const handleScroll = useCallback((event: any) => {
    const { layoutMeasurement, contentOffset, contentSize } = event.nativeEvent;
    const distanceFromBottom = contentSize.height - layoutMeasurement.height - contentOffset.y;
    const atBottom = distanceFromBottom < AT_BOTTOM_THRESHOLD;
    isAtBottomRef.current = atBottom;
    setShowScrollBtn(!atBottom);
  }, []);

  const scrollToBottom = useCallback(() => {
    listRef.current?.scrollToEnd({ animated: true });
  }, []);

  const handleSend = async (text: string, attachments: Attachment[] = []) => {
    if (!sessionCreatedRef.current) {
      sessionCreatedRef.current = true;
      try {
        await createSession(sessionId);
      } catch {
        sessionCreatedRef.current = false;
        return;
      }
    }
    sendMessage(text, attachments);
    queryClient.invalidateQueries({ queryKey: ['sessions'] });
  };

  const showEmpty = messages.length === 0;

  return (
    <SafeAreaView style={styles.safe}>
      <ChatHeader title="ARI" />

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
            <View style={styles.suggestions}>
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
          <View style={styles.flex}>
            <FlatList
              ref={listRef}
              data={messages}
              keyExtractor={(m) => m.id}
              renderItem={({ item, index }) => (
                <ChatBubble
                  role={item.role}
                  text={item.text}
                  streaming={streaming && index === messages.length - 1 && item.role === 'assistant'}
                  isError={item.isError}
                  onRetry={item.isError ? retry : undefined}
                  images={item.images}
                  docs={item.docs}
                />
              )}
              contentContainerStyle={styles.list}
              onScroll={handleScroll}
              scrollEventThrottle={100}
            />
            {showScrollBtn && (
              <TouchableOpacity
                style={[styles.scrollBtn, { backgroundColor: colors.card, borderColor: colors.border }]}
                onPress={scrollToBottom}
                activeOpacity={0.8}
              >
                <Ionicons name="chevron-down" size={20} color={colors.foreground} />
              </TouchableOpacity>
            )}
          </View>
        )}

        <ChatInput onSend={handleSend} disabled={streaming || !isConnected} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ColorTokens) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.background },
  flex: { flex: 1 },
  list: { paddingTop: 12, paddingBottom: 8 },
  scrollBtn: {
    position: 'absolute',
    bottom: 12,
    alignSelf: 'center',
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 6,
    elevation: 4,
  },
  error: { color: c.destructive, fontSize: 13, textAlign: 'center', padding: 8 },
  emptyContainer: { flexGrow: 1, paddingHorizontal: 20, paddingTop: 48, paddingBottom: 16 },
  emptyTop: { alignItems: 'center', marginBottom: 36 },
  logoCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: c.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
    shadowColor: c.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 6,
  },
  logoText: { fontSize: 28, fontWeight: '800', color: c.primaryForeground },
  greeting: { fontSize: 22, fontWeight: '700', color: c.foreground, marginBottom: 6, textAlign: 'center' },
  greetingSub: { fontSize: 14, color: c.mutedForeground, textAlign: 'center' },
  suggestions: { gap: 10 },
  chip: {
    backgroundColor: c.muted,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: c.border,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  chipText: { fontSize: 14, color: c.foreground, lineHeight: 20 },
});
