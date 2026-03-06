import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  Alert,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { useRouter } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { Ionicons } from '@expo/vector-icons';
import { getUser, clearAuth } from '../../lib/auth';
import { getBillingStatus, createPortalSession } from '../../lib/api';
import type { AuthUser } from '../../lib/auth';
import type { BillingStatus } from '../../lib/api';
import { colors } from '../../lib/colors';

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

  const tier = billing?.tier ?? 'free';
  const tierLabel = `ARI ${tier.charAt(0).toUpperCase() + tier.slice(1)}`;

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Account</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Profile card */}
        <View style={styles.profileCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {user?.email?.[0]?.toUpperCase() ?? '?'}
            </Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileEmail} numberOfLines={1}>
              {user?.email ?? '—'}
            </Text>
            <View style={styles.tierBadge}>
              <Text style={styles.tierText}>{tierLabel}</Text>
            </View>
          </View>
        </View>

        {/* Subscription */}
        <Text style={styles.sectionLabel}>SUBSCRIPTION</Text>
        <View style={styles.card}>
          <RowItem
            icon="card-outline"
            label="Manage subscription"
            onPress={handleManageBilling}
            right={
              loadingPortal ? (
                <ActivityIndicator size="small" color={colors.primary} />
              ) : (
                <Ionicons name="chevron-forward" size={16} color={colors.border} />
              )
            }
          />
        </View>

        {/* Account */}
        <Text style={styles.sectionLabel}>ACCOUNT</Text>
        <View style={styles.card}>
          <RowItem
            icon="log-out-outline"
            label="Sign out"
            onPress={handleSignOut}
            danger
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function RowItem({
  icon,
  label,
  onPress,
  right,
  danger,
}: {
  icon: string;
  label: string;
  onPress: () => void;
  right?: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <TouchableOpacity style={styles.rowItem} onPress={onPress} activeOpacity={0.6}>
      <Ionicons
        name={icon as any}
        size={20}
        color={danger ? colors.destructive : colors.mutedForeground}
        style={styles.rowIcon}
      />
      <Text style={[styles.rowLabel, danger && styles.rowLabelDanger]}>{label}</Text>
      {right ?? <Ionicons name="chevron-forward" size={16} color={colors.border} />}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.muted },
  header: {
    height: 52,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  headerTitle: { fontSize: 17, fontWeight: '700', color: colors.foreground },
  scroll: { padding: 16, gap: 0 },

  // Profile
  profileCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.background,
    borderRadius: 16,
    padding: 16,
    marginBottom: 24,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    gap: 14,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.primaryForeground,
  },
  profileInfo: { flex: 1, gap: 6 },
  profileEmail: { fontSize: 15, fontWeight: '600', color: colors.foreground },
  tierBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  tierText: { fontSize: 12, fontWeight: '700', color: colors.primaryForeground },

  sectionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.mutedForeground,
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    marginBottom: 6,
    marginTop: 8,
    paddingHorizontal: 4,
  },
  card: {
    backgroundColor: colors.background,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    overflow: 'hidden',
    marginBottom: 16,
  },
  rowItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  rowIcon: { marginRight: 12 },
  rowLabel: { flex: 1, fontSize: 15, color: colors.foreground },
  rowLabelDanger: { color: colors.destructive },
});
