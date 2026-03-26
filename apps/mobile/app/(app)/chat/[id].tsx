import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import {
  Animated,
  View,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import { ChatBubble } from '../../../components/ChatBubble';
import { ChatInput } from '../../../components/ChatInput';
import { ChatHeader } from '../../../components/ChatHeader';
import { useChatStream } from '../../../hooks/useChatStream';
import { useNetworkStatus } from '../../../hooks/useNetworkStatus';
import { getMessages, getSession, Attachment } from '../../../lib/api';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useColors } from '../../../lib/theme-context';
import { ColorTokens } from '../../../lib/colors';

const AT_BOTTOM_THRESHOLD = 50;

export default function ChatScreen() {
  const { t } = useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const listRef = useRef<FlatList>(null);
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const showBtnRef = useRef(false);
  const scrollBtnOpacity = useRef(new Animated.Value(0)).current;
  const contentHeightRef = useRef(0);
  const layoutHeightRef = useRef(0);
  const scrollOffsetRef = useRef(0);

  const { messages, streaming, sendMessage, stopStreaming, retry, loadMessages } = useChatStream(id);
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

  const checkScrollBtn = useCallback(() => {
    if (!layoutHeightRef.current) return;
    const dist = contentHeightRef.current - layoutHeightRef.current - scrollOffsetRef.current;
    const shouldShow = dist > AT_BOTTOM_THRESHOLD;
    if (shouldShow !== showBtnRef.current) {
      showBtnRef.current = shouldShow;
      scrollBtnOpacity.setValue(shouldShow ? 1 : 0);
    }
  }, [scrollBtnOpacity]);

  const handleContentSizeChange = useCallback((_: number, h: number) => {
    contentHeightRef.current = h;
    checkScrollBtn();
  }, [checkScrollBtn]);

  const handleLayout = useCallback((event: any) => {
    layoutHeightRef.current = event.nativeEvent.layout.height;
    checkScrollBtn();
  }, [checkScrollBtn]);

  const handleScroll = useCallback((event: any) => {
    const { layoutMeasurement, contentOffset, contentSize } = event.nativeEvent;
    scrollOffsetRef.current = contentOffset.y;
    layoutHeightRef.current = layoutMeasurement.height;
    contentHeightRef.current = contentSize.height;
    checkScrollBtn();
  }, [checkScrollBtn]);

  const scrollToBottom = useCallback(() => {
    const offset = Math.max(0, contentHeightRef.current - layoutHeightRef.current);
    listRef.current?.scrollToOffset({ offset, animated: true });
    showBtnRef.current = false;
    scrollBtnOpacity.setValue(0);
  }, [scrollBtnOpacity]);

  const handleSend = async (text: string, attachments: Attachment[] = []) => {
    sendMessage(text, attachments);
    setTimeout(scrollToBottom, 100);
  };

  return (
    <KeyboardAvoidingView
      style={styles.safe}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <SafeAreaView style={styles.flex} edges={['top', 'left', 'right']}>
        <ChatHeader title={session?.title ?? t('chat.defaultTitle')} showBack />

        <View style={styles.flex}>
          {isLoading ? (
            <View style={styles.loading}>
              <ActivityIndicator size="large" color={colors.primary} />
            </View>
          ) : (
            <FlatList
              ref={listRef}
              style={styles.flex}
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
              onLayout={handleLayout}
              onContentSizeChange={handleContentSizeChange}
              onScroll={handleScroll}
              scrollEventThrottle={16}
            />
          )}

          <Animated.View
            style={[styles.scrollBtn, { opacity: scrollBtnOpacity, backgroundColor: colors.card, borderColor: colors.border }]}
          >
            <TouchableOpacity onPress={scrollToBottom} activeOpacity={0.8} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
              <Ionicons name="chevron-down" size={20} color={colors.foreground} />
            </TouchableOpacity>
          </Animated.View>
        </View>

        <ChatInput onSend={handleSend} onStop={stopStreaming} streaming={streaming} disabled={isLoading || !isConnected} />
      </SafeAreaView>
    </KeyboardAvoidingView>
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
