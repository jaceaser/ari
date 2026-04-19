import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { useIAP } from 'expo-iap';
import { clearAuth, isAuthenticated } from '../../lib/auth';
import { getUserProfile, syncAppleSubscription } from '../../lib/api';
import type { UserProfile } from '../../lib/api';
import { useColors } from '../../lib/theme-context';
import { ColorTokens } from '../../lib/colors';

export default function SettingsScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const { restorePurchases } = useIAP({
    onPurchaseSuccess: async (purchase) => {
      const productId = purchase.productId as 'ari_lite' | 'ari_elite';
      if (productId !== 'ari_lite' && productId !== 'ari_elite') return;
      await syncAppleSubscription({
        product_id: productId,
        status: 'active',
        transaction_id: purchase.transactionId ?? undefined,
        original_transaction_id: purchase.originalTransactionIdentifierIOS ?? undefined,
      }).catch(() => {});
      getUserProfile().then(setProfile).catch(() => {});
    },
  });

  useFocusEffect(useCallback(() => {
    getUserProfile()
      .then(setProfile)
      .catch((err: Error) => {
        if (err.message.includes('401') || err.message.includes('403')) {
          clearAuth().then(() => router.replace('/(auth)'));
        }
      });
  }, [router]));

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

  const handleSubscribe = () => {
    router.push('/(app)/subscribe');
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

      <ScrollView style={styles.scrollBg} contentContainerStyle={styles.scroll}>
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

        {Platform.OS !== 'ios' && (
          <>
            <Text style={styles.sectionLabel}>{t('settings.subscriptionSection')}</Text>
            <View style={styles.card}>
              <RowItem
                icon="card-outline"
                label={t('settings.manageSubscription')}
                onPress={handleManageBilling}
                colors={colors}
              />
            </View>
          </>
        )}

        {Platform.OS === 'ios' && (
          <>
            <Text style={styles.sectionLabel}>SUBSCRIPTION</Text>
            <View style={styles.card}>
              {tierRaw === 'free' ? (
                <RowItem
                  icon="star-outline"
                  label="Upgrade subscription"
                  onPress={handleSubscribe}
                  colors={colors}
                />
              ) : profile?.subscription_platform === 'apple' ? (
                <>
                  {tierRaw === 'lite' && (
                    <RowItem
                      icon="star-outline"
                      label="Upgrade to Elite"
                      onPress={handleSubscribe}
                      colors={colors}
                    />
                  )}
                  <RowItem
                    icon="card-outline"
                    label="Manage subscription"
                    onPress={() => WebBrowser.openBrowserAsync('https://apps.apple.com/account/subscriptions')}
                    colors={colors}
                  />
                </>
              ) : (
                <RowItem
                  icon="card-outline"
                  label="Manage subscription"
                  onPress={() => WebBrowser.openBrowserAsync('https://billing.stripe.com/p/login/aFa7sK4J91hJ5yVbxs5kk00')}
                  colors={colors}
                />
              )}
              <RowItem
                icon="refresh-outline"
                label="Restore purchases"
                onPress={() => restorePurchases().then(() => getUserProfile().then(setProfile))}
                colors={colors}
              />
            </View>
          </>
        )}

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
  safe: { flex: 1, backgroundColor: c.background },
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
  scrollBg: { backgroundColor: c.muted },
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
