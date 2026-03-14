import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  ActivityIndicator,
  StyleSheet,
  SafeAreaView,
  TouchableOpacity,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { verifyMagicLink } from '../../lib/api';
import { saveAuth } from '../../lib/auth';
import { useColors } from '../../lib/theme-context';
import { ColorTokens } from '../../lib/colors';

export default function VerifyScreen() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  const redirectToLogin = useCallback(() => {
    router.replace('/(auth)');
  }, [router]);

  useEffect(() => {
    if (!token) {
      // Auto-redirect immediately — no token means nothing to verify
      redirectToLogin();
      return;
    }
    verifyMagicLink(token)
      .then(async (data) => {
        await saveAuth(data.token, data.user);
        router.replace('/(app)');
      })
      .catch((err: any) => {
        const msg: string = err?.message ?? '';
        if (msg.includes('401') || msg.toLowerCase().includes('expired') || msg.toLowerCase().includes('invalid')) {
          setError('This link has expired or already been used.');
        } else {
          setError('Verification failed. Please try again.');
        }
      });
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-redirect to login after 3 seconds on error
  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(redirectToLogin, 3000);
    return () => clearTimeout(timer);
  }, [error, redirectToLogin]);

  if (error) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <View style={styles.iconCircle}>
            <Ionicons name="close" size={28} color={colors.destructive} />
          </View>
          <Text style={styles.title}>Link expired</Text>
          <Text style={styles.subtitle}>{error}{'\n'}Redirecting you to sign in…</Text>
          <TouchableOpacity style={styles.button} onPress={redirectToLogin}>
            <Text style={styles.buttonText}>Sign in now</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.center}>
        <View style={styles.logoCircle}>
          <Text style={styles.logoText}>A</Text>
        </View>
        <ActivityIndicator size="large" color={colors.primary} style={{ marginBottom: 16 }} />
        <Text style={styles.label}>Signing you in…</Text>
      </View>
    </SafeAreaView>
  );
}

const makeStyles = (c: ColorTokens) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  logoCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: c.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 32,
    shadowColor: c.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 6,
  },
  logoText: { fontSize: 32, fontWeight: '800', color: c.primaryForeground },
  label: { fontSize: 16, color: c.mutedForeground },
  iconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: c.muted,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  title: { fontSize: 22, fontWeight: '700', color: c.foreground, marginBottom: 8, textAlign: 'center' },
  subtitle: { fontSize: 15, color: c.mutedForeground, textAlign: 'center', lineHeight: 22, marginBottom: 32 },
  button: {
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 12,
    backgroundColor: c.primary,
  },
  buttonText: { color: c.primaryForeground, fontSize: 16, fontWeight: '700' },
});
