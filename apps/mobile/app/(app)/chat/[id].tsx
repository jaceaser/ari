import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import { ChatBubble } from '../../../components/ChatBubble';
import { ChatInput } from '../../../components/ChatInput';
import { ChatHeader } from '../../../components/ChatHeader';
import { useChatStream } from '../../../hooks/useChatStream';
import { useNetworkStatus } from '../../../hooks/useNetworkStatus';
import { getMessages, getSession, Attachment } from '../../../lib/api';
import { useQuery } from '@tanstack/react-query';
import { useColors } from '../../../lib/theme-context';
import { ColorTokens } from '../../../lib/colors';

const AT_BOTTOM_THRESHOLD = 80;

export default function ChatScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const listRef = useRef<FlatList>(null);
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const isAtBottomRef = useRef(true);

  const { messages, streaming, sendMessage, retry, loadMessages } = useChatStream(id);
  const { isConnected } = useNetworkStatus();

  const { data: session } = useQuery({
    queryKey: ['session', id],
    queryFn: () => getSession(id),
    enabled: !!id,
  });

  const { data: historyMessages, isLoading } = useQuery({
    queryKey: ['messages', id],
    queryFn: () => getMessages(id),
    enabled: !!id,
  });

  useEffect(() => {
    if (historyMessages && historyMessages.length > 0) {
      loadMessages(historyMessages);
    }
  }, [historyMessages]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll only when user is already near the bottom
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
    sendMessage(text, attachments);
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ChatHeader title={session?.title ?? 'Chat'} showBack />

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={0}
      >
        <View style={styles.flex}>
          {isLoading ? (
            <View style={styles.loading}>
              <ActivityIndicator size="large" color={colors.primary} />
            </View>
          ) : (
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
          )}

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

        <ChatInput onSend={handleSend} disabled={streaming || isLoading || !isConnected} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ColorTokens) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.background },
  flex: { flex: 1 },
  list: { paddingTop: 12, paddingBottom: 8 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
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
});
