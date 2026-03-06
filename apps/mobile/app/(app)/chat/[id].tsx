import React, { useEffect, useRef } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
  Text,
  ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { ChatBubble } from '../../../components/ChatBubble';
import { ChatInput } from '../../../components/ChatInput';
import { ChatHeader } from '../../../components/ChatHeader';
import { useChatStream } from '../../../hooks/useChatStream';
import { getMessages, getSession } from '../../../lib/api';
import { useQuery } from '@tanstack/react-query';
import { colors } from '../../../lib/colors';

export default function ChatScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const listRef = useRef<FlatList>(null);

  const { messages, streaming, error, sendMessage, loadMessages } = useChatStream(id);

  const { data: session } = useQuery({
    queryKey: ['session', id],
    queryFn: () => getSession(id),
    enabled: !!id,
  });

  const { isLoading } = useQuery({
    queryKey: ['messages', id],
    queryFn: () => getMessages(id),
    enabled: !!id,
    select: (data) => { loadMessages(data); return data; },
  });

  useEffect(() => {
    if (messages.length > 0) listRef.current?.scrollToEnd({ animated: true });
  }, [messages]);

  return (
    <SafeAreaView style={styles.safe}>
      <ChatHeader title={session?.title ?? 'Chat'} showBack />

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={0}
      >
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
              />
            )}
            contentContainerStyle={styles.list}
          />
        )}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <ChatInput onSend={sendMessage} disabled={streaming || isLoading} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  list: { paddingTop: 12, paddingBottom: 8 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  error: { color: colors.destructive, fontSize: 13, textAlign: 'center', padding: 8 },
});
