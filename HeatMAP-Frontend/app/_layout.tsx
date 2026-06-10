import { useEffect } from 'react';
import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View, ActivityIndicator, StyleSheet, Platform } from 'react-native';
import { useFonts, OpenSans_300Light, OpenSans_400Regular, OpenSans_500Medium, OpenSans_600SemiBold, OpenSans_700Bold } from '@expo-google-fonts/open-sans';
import { Anuphan_400Regular, Anuphan_500Medium, Anuphan_600SemiBold } from '@expo-google-fonts/anuphan';
import { BaiJamjuree_600SemiBold, BaiJamjuree_700Bold } from '@expo-google-fonts/bai-jamjuree';
import 'react-native-reanimated';

import { Colors } from '@/constants/theme';
import { SettingsProvider, useSettings } from '@/hooks/useSettings';
import { registerForPushNotificationsAsync } from '@/services/NotificationService';

// Import global CSS for web (Leaflet). Must stay a conditional require so native
// builds never resolve the web-only stylesheet.
if (Platform.OS === 'web') {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require('./global.css');
}

export const unstable_settings = {
  anchor: '(tabs)',
};

// Custom theme based on Heatwave design
const CustomLightTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: Colors.light.primary,
    background: Colors.light.background,
    card: Colors.light.surface,
    text: Colors.light.text,
    border: Colors.light.border,
  },
};

const CustomDarkTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: Colors.dark.primary,
    background: Colors.dark.background,
    card: Colors.dark.surface,
    text: Colors.dark.text,
    border: Colors.dark.border,
  },
};

// Inner component that uses settings context
function AppContent({ children }: { children: React.ReactNode }) {
  const { isDarkMode } = useSettings();
  const colorScheme = isDarkMode ? 'dark' : 'light';

  return (
    <ThemeProvider value={colorScheme === 'dark' ? CustomDarkTheme : CustomLightTheme}>
      <StatusBar style={isDarkMode ? 'light' : 'dark'} />
      {children}
    </ThemeProvider>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    OpenSans_300Light,
    OpenSans_400Regular,
    OpenSans_500Medium,
    OpenSans_600SemiBold,
    OpenSans_700Bold,
    // Calm Authority: Thai-first pairing (display = Bai Jamjuree, body = Anuphan)
    Anuphan_400Regular,
    Anuphan_500Medium,
    Anuphan_600SemiBold,
    BaiJamjuree_600SemiBold,
    BaiJamjuree_700Bold,
  });

  useEffect(() => {
    registerForPushNotificationsAsync().then(token => console.log("Init Push Token: ", token));

    /*
    const notificationListener = Notifications.addNotificationReceivedListener(notification => {
      console.log('Notification received in foreground:', notification);
    });

    const responseListener = Notifications.addNotificationResponseReceivedListener(response => {
      console.log('User interacted with notification:', response);
    });

    return () => {
      Notifications.removeNotificationSubscription(notificationListener);
      Notifications.removeNotificationSubscription(responseListener);
    };
    */
  }, []);

  if (!fontsLoaded) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  return (
    <SettingsProvider>
      <AppContent>
        <Stack>
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
          <Stack.Screen name="prd" options={{ presentation: 'modal', title: 'Product Requirements' }} />
          <Stack.Screen name="checklist" options={{ presentation: 'modal', headerShown: false }} />
          <Stack.Screen name="liff" options={{ headerShown: false }} />
        </Stack>
      </AppContent>
    </SettingsProvider>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
  },
});
