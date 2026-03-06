import '../global.css';
import { useEffect, useState } from 'react';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { isAuthenticated } from '../lib/auth';
import { useRouter } from 'expo-router';

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const router = useRouter();

  useEffect(() => {
    isAuthenticated().then((ok) => {
      setAuthed(ok);
      setReady(true);
      SplashScreen.hideAsync();
    });
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (authed) {
      router.replace('/(app)');
    } else {
      router.replace('/(auth)');
    }
  }, [ready, authed]);

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(auth)" />
      <Stack.Screen name="(app)" />
    </Stack>
  );
}
