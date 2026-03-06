import React, { useState } from 'react';
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
import { useRouter } from 'expo-router';
import { sendMagicLink, verifyMagicLink } from '../../lib/api';
import { saveAuth } from '../../lib/auth';

export default function LoginScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [token, setToken] = useState('');
  const [verifying, setVerifying] = useState(false);

  const handleSend = async () => {
    const trimmed = email.trim().toLowerCase();
    if (!trimmed || !trimmed.includes('@')) {
      Alert.alert('Invalid email', 'Please enter a valid email address.');
      return;
    }
    setLoading(true);
    try {
      await sendMagicLink(trimmed);
      setSent(true);
    } catch (err: any) {
      Alert.alert('Error', err?.message ?? 'Failed to send magic link. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyToken = async () => {
    const t = token.trim();
    if (!t) return;
    setVerifying(true);
    try {
      const data = await verifyMagicLink(t);
      await saveAuth(data.token, data.user);
      router.replace('/(app)');
    } catch (err: any) {
      Alert.alert('Invalid token', err?.message ?? 'Token is invalid or expired.');
    } finally {
      setVerifying(false);
    }
  };

  if (sent) {
    return (
      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.kav}
        >
          <View style={styles.center}>
            <Text style={styles.emoji}>📬</Text>
            <Text style={styles.title}>Check your email</Text>
            <Text style={styles.subtitle}>
              We sent a sign-in link to{'\n'}
              <Text style={styles.emailHighlight}>{email}</Text>
            </Text>

            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>or paste your token</Text>
              <View style={styles.dividerLine} />
            </View>

            <TextInput
              style={styles.input}
              value={token}
              onChangeText={setToken}
              placeholder="Paste token from email link"
              placeholderTextColor="#9ca3af"
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
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.buttonText}>Sign in with token</Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity style={styles.linkButton} onPress={() => { setSent(false); setToken(''); }}>
              <Text style={styles.linkText}>Use a different email</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.kav}
      >
        <View style={styles.center}>
          <Text style={styles.logo}>ARI</Text>
          <Text style={styles.title}>Sign in</Text>
          <Text style={styles.subtitle}>
            Enter your email to receive a magic link
          </Text>

          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            placeholder="you@example.com"
            placeholderTextColor="#9ca3af"
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="send"
            onSubmitEditing={handleSend}
          />

          <TouchableOpacity
            style={[styles.button, (!email.trim() || loading) && styles.buttonDisabled]}
            onPress={handleSend}
            disabled={!email.trim() || loading}
          >
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Send magic link</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#fff' },
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
    color: '#1a56db',
    letterSpacing: -1,
    marginBottom: 24,
  },
  emoji: { fontSize: 48, marginBottom: 16 },
  title: {
    fontSize: 26,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 15,
    color: '#6b7280',
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 32,
  },
  emailHighlight: { fontWeight: '600', color: '#111827' },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    width: '100%',
    marginBottom: 16,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: '#e5e7eb' },
  dividerText: { marginHorizontal: 12, fontSize: 13, color: '#9ca3af' },
  input: {
    width: '100%',
    height: 52,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: '#e5e7eb',
    paddingHorizontal: 16,
    fontSize: 16,
    color: '#111827',
    backgroundColor: '#f9fafb',
    marginBottom: 16,
  },
  button: {
    width: '100%',
    height: 52,
    borderRadius: 12,
    backgroundColor: '#1a56db',
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonDisabled: { backgroundColor: '#93c5fd' },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  linkButton: { marginTop: 24 },
  linkText: { color: '#1a56db', fontSize: 15 },
});
