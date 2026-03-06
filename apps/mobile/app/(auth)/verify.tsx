import React, { useEffect, useState } from 'react';
import { View, Text, ActivityIndicator, StyleSheet, SafeAreaView } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { verifyMagicLink } from '../../lib/api';
import { saveAuth } from '../../lib/auth';

export default function VerifyScreen() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError('Missing token. Please request a new magic link.');
      return;
    }
    verifyMagicLink(token)
      .then(async (data) => {
        await saveAuth(data.token, data.user);
        router.replace('/(app)');
      })
      .catch((err) => {
        setError(err?.message ?? 'Verification failed. Please try again.');
      });
  }, [token]);

  if (error) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.center}>
          <Text style={styles.emoji}>❌</Text>
          <Text style={styles.title}>Link expired</Text>
          <Text style={styles.subtitle}>{error}</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1a56db" />
        <Text style={styles.label}>Signing you in…</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#fff' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  emoji: { fontSize: 48, marginBottom: 16 },
  title: { fontSize: 22, fontWeight: '700', color: '#111827', marginBottom: 8 },
  subtitle: { fontSize: 15, color: '#6b7280', textAlign: 'center', lineHeight: 22 },
  label: { marginTop: 16, fontSize: 15, color: '#6b7280' },
});
