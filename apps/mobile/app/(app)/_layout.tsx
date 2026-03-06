import { Stack } from 'expo-router';
import { View, StyleSheet } from 'react-native';
import { SidebarProvider } from '../../lib/sidebar-context';
import { SidebarOverlay } from '../../components/Sidebar';

export default function AppLayout() {
  return (
    <SidebarProvider>
      <View style={styles.root}>
        <Stack screenOptions={{ headerShown: false, animation: 'slide_from_right' }} />
        <SidebarOverlay />
      </View>
    </SidebarProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
