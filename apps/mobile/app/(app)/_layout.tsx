import { Stack, useRouter } from 'expo-router';
import { View, StyleSheet } from 'react-native';
import { useEffect } from 'react';
import { SidebarProvider } from '../../lib/sidebar-context';
import { SidebarOverlay } from '../../components/Sidebar';
import { OfflineBanner } from '../../components/OfflineBanner';
import { useNetworkStatus } from '../../hooks/useNetworkStatus';
import { isAuthenticated } from '../../lib/auth';

function AppLayoutInner() {
  const { isConnected, ready } = useNetworkStatus();
  const router = useRouter();

  // Guard: redirect to login if token is missing or expired
  useEffect(() => {
    isAuthenticated().then((ok) => {
      if (!ok) router.replace('/(auth)');
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <View style={styles.root}>
      <Stack screenOptions={{ headerShown: false, animation: 'slide_from_right' }} />
      <SidebarOverlay />
      {ready && <OfflineBanner visible={!isConnected} />}
    </View>
  );
}

export default function AppLayout() {
  return (
    <SidebarProvider>
      <AppLayoutInner />
    </SidebarProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
