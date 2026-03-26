import '../lib/i18n';
import '../global.css';
import { useEffect, useRef, useState } from 'react';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import * as Linking from 'expo-linking';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { isAuthenticated } from '../lib/auth';
import { useRouter } from 'expo-router';
import { ThemeProvider } from '../lib/theme-context';

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient();

/**
 * Extract a magic-link verify token from an incoming URL.
 * Handles both:
 *   ari://verify?token=XXX          (custom scheme — works today)
 *   https://reilabs.ai/auth/verify?token=XXX  (Universal / App Link)
 */
function extractVerifyToken(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = Linking.parse(url);
    const token = parsed.queryParams?.token;
    if (typeof token === 'string' && token.length > 0) {
      const path = parsed.path ?? '';
      if (path === 'verify' || path.endsWith('/verify') || path.endsWith('/auth/verify')) {
        return token;
      }
    }
  } catch {}
  return null;
}

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const router = useRouter();
  const initialNavDoneRef = useRef(false);

  useEffect(() => {
    isAuthenticated().then((ok) => {
      setAuthed(ok);
      setReady(true);
      SplashScreen.hideAsync();
    });
  }, []);

  // Cold-start navigation: check for a deep link before deciding where to go
  useEffect(() => {
    if (!ready) return;
    Linking.getInitialURL().then((url) => {
      initialNavDoneRef.current = true;
      const token = extractVerifyToken(url);
      if (token) {
        router.replace({ pathname: '/(auth)/verify', params: { token } });
      } else if (authed) {
        // Already on the welcome screen when not authed — no navigation needed
        router.replace('/(app)');
      }
    });
  }, [ready]); // eslint-disable-line react-hooks/exhaustive-deps

  // Foreground deep-link: handle magic links when the app is already running
  useEffect(() => {
    const subscription = Linking.addEventListener('url', ({ url }) => {
      const token = extractVerifyToken(url);
      if (token) {
        router.replace({ pathname: '/(auth)/verify', params: { token } });
      }
    });
    return () => subscription.remove();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <Stack screenOptions={{ headerShown: false }}>
            <Stack.Screen name="(auth)" />
            <Stack.Screen name="(app)" />
          </Stack>
        </ThemeProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
