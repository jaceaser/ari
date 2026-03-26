import React, { useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { clearAuth, isAuthenticated } from '../../lib/auth';
import { getUserProfile } from '../../lib/api';
import type { UserProfile } from '../../lib/api';
import { useColors } from '../../lib/theme-context';
import { ColorTokens } from '../../lib/colors';

export default function SettingsScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);

  useEffect(() => {
    getUserProfile()
      .then(setProfile)
      .catch((err: Error) => {
        if (err.message.includes('401') || err.message.includes('403')) {
          clearAuth().then(() => router.replace('/(auth)'));
        }
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSignOut = () => {
    Alert.alert(t('settings.signOutConfirmTitle'), t('settings.signOutConfirmMessage'), [
      { text: t('settings.signOutConfirmCancel'), style: 'cancel' },
      {
        text: t('settings.signOutConfirmAction'),
        style: 'destructive',
        onPress: async () => {
          await clearAuth();
          router.replace('/(auth)');
        },
      },
    ]);
  };

  const handleManageBilling = async () => {
    await WebBrowser.openBrowserAsync('https://billing.stripe.com/p/login/aFa7sK4J91hJ5yVbxs5kk00');
  };

  const tierRaw = profile?.tier ?? 'free';
  const tierLabel = `ARI ${tierRaw.charAt(0).toUpperCase() + tierRaw.slice(1)}`;
  const initial = profile?.email?.[0]?.toUpperCase() ?? '?';

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.headerBtn} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={24} color={colors.foreground} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t('settings.title')}</Text>
        <View style={styles.headerBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.profileCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initial}</Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileEmail} numberOfLines={1}>
              {profile?.email ?? '—'}
            </Text>
            <View style={styles.tierBadge}>
              <Text style={styles.tierText}>{tierLabel}</Text>
            </View>
          </View>
        </View>

        <Text style={styles.sectionLabel}>{t('settings.subscriptionSection')}</Text>
        <View style={styles.card}>
          <RowItem
            icon="card-outline"
            label={t('settings.manageSubscription')}
            onPress={handleManageBilling}
            colors={colors}
          />
        </View>

        <Text style={styles.sectionLabel}>{t('settings.accountSection')}</Text>
        <View style={styles.card}>
          <RowItem icon="log-out-outline" label={t('settings.signOut')} onPress={handleSignOut} colors={colors} danger />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function RowItem({ icon, label, onPress, right, danger, colors }: {
  icon: string; label: string; onPress: () => void;
  right?: React.ReactNode; danger?: boolean; colors: ColorTokens;
}) {
  return (
    <TouchableOpacity
      style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14 }}
      onPress={onPress}
      activeOpacity={0.6}
    >
      <Ionicons
        name={icon as any}
        size={20}
        color={danger ? colors.destructive : colors.mutedForeground}
        style={{ marginRight: 12 }}
      />
      <Text style={{ flex: 1, fontSize: 15, color: danger ? colors.destructive : colors.foreground }}>
        {label}
      </Text>
      {right ?? <Ionicons name="chevron-forward" size={16} color={colors.border} />}
    </TouchableOpacity>
  );
}

const makeStyles = (c: ColorTokens) => StyleSheet.create({
  safe: { flex: 1, backgroundColor: c.muted },
  header: {
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: c.border,
    backgroundColor: c.background,
  },
  headerBtn: { width: 44, alignItems: 'center' },
  headerTitle: { flex: 1, fontSize: 17, fontWeight: '700', color: c.foreground, textAlign: 'center' },
  scroll: { padding: 16 },
  profileCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: c.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 24,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: c.border,
    gap: 14,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: c.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontSize: 22, fontWeight: '700', color: c.primaryForeground },
  profileInfo: { flex: 1, gap: 6 },
  profileEmail: { fontSize: 15, fontWeight: '600', color: c.foreground },
  tierBadge: {
    alignSelf: 'flex-start',
    backgroundColor: c.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  tierText: { fontSize: 12, fontWeight: '700', color: c.primaryForeground },
  sectionLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: c.mutedForeground,
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    marginBottom: 6,
    marginTop: 8,
    paddingHorizontal: 4,
  },
  card: {
    backgroundColor: c.card,
    borderRadius: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: c.border,
    overflow: 'hidden',
    marginBottom: 16,
  },
});
