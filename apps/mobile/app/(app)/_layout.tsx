import { Stack } from 'expo-router';
import { View, StyleSheet } from 'react-native';
import { SidebarProvider } from '../../lib/sidebar-context';
import { SidebarOverlay } from '../../components/Sidebar';
import { OfflineBanner } from '../../components/OfflineBanner';
import { useNetworkStatus } from '../../hooks/useNetworkStatus';

function AppLayoutInner() {
  const { isConnected, ready } = useNetworkStatus();

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
