import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Platform, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useRouter } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import { useIAP } from 'expo-iap';
import { getUserProfile, syncAppleSubscription } from '../../lib/api';
import { useColors } from '../../lib/theme-context';
import { ColorTokens } from '../../lib/colors';

const PRODUCTS = ['ari_lite', 'ari_elite'] as const;
const TERMS_URL = 'https://reilabs.ai/terms-of-service';
const PRIVACY_URL = 'https://reilabs.ai/privacy-policy';

export default function SubscribeScreen() {
  const router = useRouter();
  const colors = useColors();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const [currentTier, setCurrentTier] = useState<string>('free');

  useFocusEffect(useCallback(() => {
    getUserProfile().then((p) => setCurrentTier(p.tier ?? 'free')).catch(() => {});
  }, []));

  const {
    connected,
    subscriptions,
    fetchProducts,
    requestPurchase,
    finishTransaction,
    restorePurchases,
  } = useIAP({
    onPurchaseSuccess: async (purchase) => {
      const productId = purchase.productId as 'ari_lite' | 'ari_elite';
      if (productId !== 'ari_lite' && productId !== 'ari_elite') return;
      // Always finish the Apple transaction first — if we don't, StoreKit will
      // keep re-delivering it on every app launch. Then sync to backend.
      try {
        await finishTransaction({ purchase, isConsumable: false });
      } catch {
        // Ignore — transaction may already be finished
      }
      try {
        await syncAppleSubscription({
          product_id: productId,
          status: 'active',
          transaction_id: purchase.transactionId ?? undefined,
          original_transaction_id: purchase.originalTransactionIdentifierIOS ?? undefined,
        });
        Alert.alert('Subscription active', 'Your subscription is now active.');
        router.back();
      } catch {
        Alert.alert(
          'Subscription purchased',
          'Your purchase was successful, but we had trouble activating your account. Please tap "Restore" to sync your subscription.',
        );
      }
    },
    onPurchaseError: (error) => {
      Alert.alert('Purchase failed', error.message);
    },
  });

  useEffect(() => {
    if (!connected || Platform.OS !== 'ios') return;
    fetchProducts({ skus: [...PRODUCTS], type: 'subs' })
      .catch(() => {
        Alert.alert('Store unavailable', 'Unable to load subscription products right now.');
      });
  }, [connected, fetchProducts]);

  const byId = useMemo(() => {
    const map = new Map<string, (typeof subscriptions)[number]>();
    for (const item of subscriptions) map.set(item.id, item);
    return map;
  }, [subscriptions]);

  const buy = async (productId: 'ari_lite' | 'ari_elite') => {
    await requestPurchase({
      request: { ios: { sku: productId } },
      type: 'subs',
    });
  };

  if (Platform.OS !== 'ios') {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.headerBtn} onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={24} color={colors.foreground} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Subscribe</Text>
          <View style={styles.headerBtn} />
        </View>
        <View style={styles.androidWrap}>
          <Text style={styles.androidText}>Continue subscription purchase on web.</Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={() => WebBrowser.openBrowserAsync('https://reilabs.ai/products/')}>
            <Text style={styles.primaryBtnText}>Open subscription page</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.headerBtn} onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={24} color={colors.foreground} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Subscribe</Text>
        <TouchableOpacity style={styles.headerBtn} onPress={() => restorePurchases()}>
          <Text style={styles.link}>Restore</Text>
        </TouchableOpacity>
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        {PRODUCTS.map((productId) => {
          const product = byId.get(productId);
          const tierName = productId === 'ari_lite' ? 'lite' : 'elite';
          const isCurrent = currentTier === tierName;
          return (
            <View key={productId} style={[styles.card, isCurrent && styles.currentCard]}>
              <View style={styles.planHeader}>
                <Text style={styles.planTitle}>{productId === 'ari_lite' ? 'ARI Lite' : 'ARI Elite'}</Text>
                {isCurrent && <Text style={styles.currentBadge}>Current Plan</Text>}
              </View>
              <Text style={styles.price}>{product?.displayPrice ?? 'Loading...'}</Text>
              <TouchableOpacity
                style={[styles.primaryBtn, (!product || isCurrent) && styles.disabledBtn]}
                disabled={!product || isCurrent}
                onPress={() => buy(productId)}
              >
                <Text style={styles.primaryBtnText}>{isCurrent ? 'Subscribed' : 'Subscribe'}</Text>
              </TouchableOpacity>
            </View>
          );
        })}

        <View style={styles.footerLinks}>
          <TouchableOpacity onPress={() => WebBrowser.openBrowserAsync(TERMS_URL)}>
            <Text style={styles.link}>Terms of Use</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => WebBrowser.openBrowserAsync(PRIVACY_URL)}>
            <Text style={styles.link}>Privacy Policy</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
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
  },
  headerBtn: { minWidth: 72, alignItems: 'center' },
  headerTitle: { flex: 1, textAlign: 'center', fontSize: 17, fontWeight: '700', color: c.foreground },
  content: { padding: 16, gap: 12 },
  card: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: c.border,
    backgroundColor: c.card,
    borderRadius: 14,
    padding: 16,
    gap: 8,
  },
  currentCard: { borderColor: c.primary, borderWidth: 2 },
  planHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  planTitle: { fontSize: 18, fontWeight: '700', color: c.foreground },
  currentBadge: { fontSize: 12, fontWeight: '700', color: c.primary },
  price: { fontSize: 24, fontWeight: '800', color: c.primary },
  primaryBtn: {
    marginTop: 8,
    backgroundColor: c.primary,
    borderRadius: 10,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
  },
  disabledBtn: { opacity: 0.5 },
  primaryBtnText: { color: c.primaryForeground, fontWeight: '700', fontSize: 15 },
  footerLinks: { marginTop: 18, gap: 12, alignItems: 'center' },
  link: { color: c.primary, fontWeight: '600' },
  androidWrap: { flex: 1, justifyContent: 'center', padding: 20, gap: 12 },
  androidText: { color: c.mutedForeground, textAlign: 'center', fontSize: 15 },
});
