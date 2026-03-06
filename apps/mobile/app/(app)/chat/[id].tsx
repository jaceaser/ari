import React, { useEffect, useRef } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
  Text,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { ChatBubble } from '../../../components/ChatBubble';
import { ChatInput } from '../../../components/ChatInput';
import { useChatStream } from '../../../hooks/useChatStream';
import { getMessages, getSession } from '../../../lib/api';
import { useQuery } from '@tanstack/react-query';
import { colors } from '../../../lib/colors';

export default function ChatScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
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
    select: (data) => {
      loadMessages(data);
      return data;
    },
  });

  useEffect(() => {
    if (messages.length > 0) {
      listRef.current?.scrollToEnd({ animated: true });
    }
  }, [messages]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={24} color={colors.primary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {session?.title ?? 'Chat'}
        </Text>
        <View style={styles.backBtn} />
      </View>

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
        {error && <Text style={styles.errorText}>{error}</Text>}
        <ChatInput onSend={sendMessage} disabled={streaming || isLoading} />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  header: {
    height: 52,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
  },
  backBtn: { width: 44, alignItems: 'center' },
  headerTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: colors.foreground,
    textAlign: 'center',
  },
  list: { paddingTop: 16, paddingBottom: 8 },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  errorText: {
    color: colors.destructive,
    fontSize: 13,
    textAlign: 'center',
    padding: 8,
  },
});
