import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  Alert,
  View,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Keyboard,
  Platform,
  Text,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Crypto from 'expo-crypto';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'expo-router';
import { ChatBubble } from '../../components/ChatBubble';
import { ChatInput } from '../../components/ChatInput';
import { ChatHeader } from '../../components/ChatHeader';
import { useChatStream } from '../../hooks/useChatStream';
import { useNetworkStatus } from '../../hooks/useNetworkStatus';
import { createSession, Attachment } from '../../lib/api';
import { useColors } from '../../lib/theme-context';
import { ColorTokens } from '../../lib/colors';

const AT_BOTTOM_THRESHOLD = 50;

export default function NewChatScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const [sessionId] = useState(() => Crypto.randomUUID());
  const sessionCreatedRef = useRef(false);
  const { messages, streaming, sendMessage, stopStreaming, retry } = useChatStream(sessionId, {
    onFreeTierLimitReached: () => {
      Alert.alert(
        'Daily limit reached',
        'You have used all free prompts for today. Upgrade to continue.',
        [
          { text: 'Not now', style: 'cancel' },
          { text: 'Upgrade', onPress: () => router.push('/(app)/subscribe') },
        ],
      );
    },
  });
  const { isConnected } = useNetworkStatus();
  const listRef = useRef<FlatList>(null);
  const queryClient = useQueryClient();
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const SUGGESTIONS = useMemo(() => [
    t('home.suggestion1'),
    t('home.suggestion2'),
    t('home.suggestion3'),
    t('home.suggestion4'),
  ], [t]);
  const showBtnRef = useRef(false);
  const scrollBtnOpacity = useRef(new Animated.Value(0)).current;
  const contentHeightRef = useRef(0);
  const layoutHeightRef = useRef(0);
  const scrollOffsetRef = useRef(0);

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
    setTimeout(scrollToBottom, 100);
  };

  const showEmpty = messages.length === 0;

  return (
    <KeyboardAvoidingView
      style={styles.safe}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <SafeAreaView style={styles.flex} edges={['top', 'left', 'right']}>
        <ChatHeader title="ARI" />

        {showEmpty ? (
          <ScrollView
            style={styles.flex}
            contentContainerStyle={styles.emptyContainer}
            keyboardShouldPersistTaps="handled"
          >
            <View style={styles.emptyTop}>
              <View style={styles.logoCircle}>
                <Text style={styles.logoText}>A</Text>
              </View>
              <Text style={styles.greeting}>{t('home.greeting')}</Text>
              <Text style={styles.greetingSub}>{t('home.sub')}</Text>
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
            <Animated.View
              style={[styles.scrollBtn, { opacity: scrollBtnOpacity, backgroundColor: colors.card, borderColor: colors.border }]}
            >
              <TouchableOpacity onPress={scrollToBottom} activeOpacity={0.8} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
                <Ionicons name="chevron-down" size={20} color={colors.foreground} />
              </TouchableOpacity>
            </Animated.View>
          </View>
        )}

        <ChatInput onSend={handleSend} onStop={stopStreaming} streaming={streaming} disabled={!isConnected} />
      </SafeAreaView>
    </KeyboardAvoidingView>
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
