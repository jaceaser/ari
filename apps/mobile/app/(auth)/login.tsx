import React, { useMemo, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
  SafeAreaView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useTranslation } from 'react-i18next';
import { sendMagicLink, verifyMagicLink, verifyReviewCode } from '../../lib/api';
import { saveAuth } from '../../lib/auth';
import { useColors } from '../../lib/theme-context';
import { ColorTokens } from '../../lib/colors';

type SendStatus = 'pending' | 'ok' | 'error' | 'rate_limited';

export default function LoginScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const params = useLocalSearchParams<{ redirectTo?: string }>();
  const postLoginRoute = typeof params.redirectTo === 'string' && params.redirectTo
    ? params.redirectTo
    : '/(app)';
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [sendStatus, setSendStatus] = useState<SendStatus>('pending');
  const [token, setToken] = useState('');
  const [verifying, setVerifying] = useState(false);
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const fireSend = (trimmed: string) => {
    setSendStatus('pending');
    sendMagicLink(trimmed)
      .then(() => setSendStatus('ok'))
      .catch((err: any) => {
        const msg: string = err?.message ?? '';
        if (msg.includes('429') || msg.toLowerCase().includes('too many')) {
          setSendStatus('rate_limited');
        } else {
          setSendStatus('error');
        }
      });
  };

  const handleSend = async () => {
    const trimmed = email.trim();
    if (!trimmed) return;

    // If the input has no @, treat it as a reviewer access code
    if (!trimmed.includes('@')) {
      setVerifying(true);
      try {
        const data = await verifyReviewCode(trimmed.toUpperCase());
        await saveAuth(data.token, data.user);
        router.replace(postLoginRoute as any);
      } catch (err: any) {
        Alert.alert('Invalid code', err?.message ?? 'Code is invalid or expired.');
      } finally {
        setVerifying(false);
      }
      return;
    }

    // Normal magic-link flow
    setSent(true);
    fireSend(trimmed.toLowerCase());
  };

  const handleRetry = () => {
    fireSend(email.trim().toLowerCase());
  };

  const handleVerifyToken = async () => {
    const t = token.trim();
    if (!t) return;
    setVerifying(true);
    try {
      const data = await verifyMagicLink(t);
      await saveAuth(data.token, data.user);
      router.replace(postLoginRoute as any);
    } catch (err: any) {
      Alert.alert('Invalid token', err?.message ?? 'Token is invalid or expired.');
    } finally {
      setVerifying(false);
    }
  };

  const handleSubscribe = async () => {
    await WebBrowser.openBrowserAsync('https://reilabs.ai/products/');
  };

  if (sent) {
    return (
      <SafeAreaView style={styles.safe}>
        <TouchableOpacity style={styles.backButton} onPress={() => { setSent(false); setToken(''); setSendStatus('pending'); }}>
          <Ionicons name="chevron-back" size={24} color={colors.foreground} />
        </TouchableOpacity>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.kav}>
          <View style={styles.center}>
            <Text style={styles.logo}>ARI</Text>
            <Text style={styles.emoji}>📬</Text>
            <Text style={styles.title}>{t('auth.checkEmail')}</Text>

            {sendStatus === 'pending' && (
              <View style={styles.statusRow}>
                <ActivityIndicator size="small" color={colors.mutedForeground} />
                <Text style={styles.statusText}>{t('auth.sendingLink', { email })}</Text>
              </View>
            )}
            {sendStatus === 'ok' && (
              <Text style={styles.subtitle}>
                {t('auth.linkSentMessage')}{' '}
                <Text style={styles.emailHighlight}>{email}</Text>
                .{'\n'}{t('auth.linkSentSuffix')}
              </Text>
            )}
            {sendStatus === 'rate_limited' && (
              <Text style={[styles.subtitle, styles.errorText]}>
                {t('auth.rateLimited')}
              </Text>
            )}
            {sendStatus === 'error' && (
              <View style={styles.errorRow}>
                <Text style={[styles.subtitle, styles.errorText]}>
                  {t('auth.sendError')}{' '}
                </Text>
                <TouchableOpacity onPress={handleRetry}>
                  <Text style={styles.retryText}>{t('auth.tryAgain')}</Text>
                </TouchableOpacity>
              </View>
            )}

            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>{t('auth.pasteToken')}</Text>
              <View style={styles.dividerLine} />
            </View>

            <TextInput
              style={styles.input}
              value={token}
              onChangeText={setToken}
              placeholder={t('auth.tokenPlaceholder')}
              placeholderTextColor={colors.mutedForeground}
              autoCapitalize="none"
              autoCorrect={false}
              returnKeyType="go"
              onSubmitEditing={handleVerifyToken}
            />

            <TouchableOpacity
              style={[styles.button, (!token.trim() || verifying) && styles.buttonDisabled]}
              onPress={handleVerifyToken}
              disabled={!token.trim() || verifying}
            >
              {verifying ? (
                <ActivityIndicator color={colors.primaryForeground} />
              ) : (
                <Text style={styles.buttonText}>{t('auth.signInWithToken')}</Text>
              )}
            </TouchableOpacity>

            {Platform.OS !== 'ios' && (
              <View style={styles.subscribeBanner}>
                <Text style={styles.subscribeBannerText}>{t('auth.noSubscription')}</Text>
                <TouchableOpacity onPress={handleSubscribe}>
                  <Text style={styles.subscribeBannerLink}>{t('auth.subscribeHere')}</Text>
                </TouchableOpacity>
              </View>
            )}

            <TouchableOpacity style={styles.linkButton} onPress={() => { setSent(false); setToken(''); setSendStatus('pending'); }}>
              <Text style={styles.linkText}>{t('auth.differentEmail')}</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
        <Ionicons name="chevron-back" size={24} color={colors.foreground} />
      </TouchableOpacity>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.kav}>
        <View style={styles.center}>
          <Text style={styles.logo}>ARI</Text>
          <Text style={styles.title}>{t('auth.signInTitle')}</Text>
          <Text style={styles.subtitle}>{t('auth.signInSubtitle')}</Text>

          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder={t('auth.emailPlaceholder')}
            placeholderTextColor={colors.mutedForeground}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="send"
            onSubmitEditing={handleSend}
          />

          <TouchableOpacity
            style={[styles.button, (!email.trim() || verifying) && styles.buttonDisabled]}
            onPress={handleSend}
            disabled={!email.trim() || verifying}
          >
            {verifying
              ? <ActivityIndicator color={colors.primaryForeground} />
              : <Text style={styles.buttonText}>{t('auth.sendLink')}</Text>
            }
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const makeStyles = (c: ColorTokens) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.background },
  backButton: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 4,
    alignSelf: 'flex-start',
  },
  kav: { flex: 1 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  logo: {
    fontSize: 40,
    fontWeight: '800',
    color: c.primary,
    letterSpacing: 2,
    marginBottom: 24,
  },
  emoji: { fontSize: 40, marginBottom: 12 },
  title: {
    fontSize: 26,
    fontWeight: '700',
    color: c.foreground,
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 15,
    color: c.mutedForeground,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 32,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 32,
  },
  statusText: {
    fontSize: 14,
    color: c.mutedForeground,
  },
  errorRow: {
    alignItems: 'center',
    marginBottom: 32,
  },
  errorText: {
    color: c.destructive,
    marginBottom: 0,
  },
  retryText: {
    color: c.primary,
    fontSize: 15,
    fontWeight: '600',
  },
  emailHighlight: { fontWeight: '600', color: c.foreground },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    width: '100%',
    marginBottom: 16,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: c.border },
  dividerText: { marginHorizontal: 12, fontSize: 13, color: c.mutedForeground },
  input: {
    width: '100%',
    height: 52,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: c.border,
    paddingHorizontal: 16,
    fontSize: 16,
    color: c.foreground,
    backgroundColor: c.muted,
    marginBottom: 16,
  },
  button: {
    width: '100%',
    height: 52,
    borderRadius: 12,
    backgroundColor: c.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonDisabled: { opacity: 0.5 },
  buttonText: { color: c.primaryForeground, fontSize: 16, fontWeight: '700' },
  subscribeBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 28,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    backgroundColor: c.muted,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: c.border,
  },
  subscribeBannerText: {
    fontSize: 14,
    color: c.mutedForeground,
  },
  subscribeBannerLink: {
    fontSize: 14,
    fontWeight: '700',
    color: c.primary,
  },
  linkButton: { marginTop: 20 },
  linkText: { color: c.primary, fontSize: 15, fontWeight: '600' },
});
