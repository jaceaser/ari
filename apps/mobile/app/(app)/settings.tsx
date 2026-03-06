import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { getUser, clearAuth } from '../../lib/auth';
import { getBillingStatus, createPortalSession } from '../../lib/api';
import type { AuthUser } from '../../lib/auth';
import type { BillingStatus } from '../../lib/api';

export default function SettingsScreen() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [loadingPortal, setLoadingPortal] = useState(false);

  useEffect(() => {
    getUser().then(setUser);
    getBillingStatus().then(setBilling).catch(() => {});
  }, []);

  const handleSignOut = () => {
    Alert.alert('Sign out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Sign out',
        style: 'destructive',
        onPress: async () => {
          await clearAuth();
          router.replace('/(auth)');
        },
      },
    ]);
  };

  const handleManageBilling = async () => {
    setLoadingPortal(true);
    try {
      const { url } = await createPortalSession();
      await WebBrowser.openBrowserAsync(url);
    } catch {
      Alert.alert('Error', 'Could not open billing portal. Try again.');
    } finally {
      setLoadingPortal(false);
    }
  };

  const tierLabel = billing?.tier
    ? `ARI ${billing.tier.charAt(0).toUpperCase() + billing.tier.slice(1)}`
    : 'Free';

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Account</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionLabel}>ACCOUNT</Text>
        <View style={styles.card}>
          <Row label="Email" value={user?.email ?? '—'} />
          <Divider />
          <Row label="Plan" value={tierLabel} />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionLabel}>SUBSCRIPTION</Text>
        <View style={styles.card}>
          <TouchableOpacity style={styles.row} onPress={handleManageBilling} disabled={loadingPortal}>
            <Text style={styles.rowLabel}>Manage subscription</Text>
            {loadingPortal ? (
              <ActivityIndicator size="small" color="#1a56db" />
            ) : (
              <Text style={styles.rowChevron}>›</Text>
            )}
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.section}>
        <View style={styles.card}>
          <TouchableOpacity style={styles.row} onPress={handleSignOut}>
            <Text style={[styles.rowLabel, styles.danger]}>Sign out</Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

function Divider() {
  return <View style={styles.divider} />;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f3f4f6' },
  header: {
    height: 52,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#fff',
  },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#111827' },
  section: { marginTop: 24, paddingHorizontal: 16 },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6b7280',
    marginBottom: 6,
    letterSpacing: 0.5,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  rowLabel: { fontSize: 15, color: '#111827' },
  rowValue: { fontSize: 15, color: '#6b7280' },
  rowChevron: { fontSize: 20, color: '#d1d5db' },
  divider: { height: 1, backgroundColor: '#f3f4f6' },
  danger: { color: '#dc2626' },
});
