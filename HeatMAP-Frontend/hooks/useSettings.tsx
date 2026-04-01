/**
 * Global Settings Context
 * Manages Theme (Dark/Light), Language (Thai/English), and Font Size (S/M/L)
 */

import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect, useMemo } from 'react';
import { Appearance, useColorScheme, Platform } from 'react-native';
import { translations as i18nTranslations, TranslationKey } from '@/i18n/translations';
import { createTypography, FONT_SIZE_SCALE, BASE_FONT_SIZES } from '@/constants/theme';

// Check if we're on a native platform (iOS/Android)
const isNativePlatform = Platform.OS !== 'web';

// Types
export type ThemeMode = 'light' | 'dark' | 'system';
export type Language = 'en' | 'th';
export type FontSize = 'small' | 'default' | 'large';

// Global singleton for non-React files to read settings synchronously
export const GlobalSettings = {
  pushNotifications: true,
  hapticFeedback: false,
};

// Storage keys - Using a simple in-memory approach for persistence
const STORAGE_KEYS = {
  THEME_MODE: 'theme_mode',
  LANGUAGE: 'language',
  FONT_SIZE: 'font_size',
};

// Font size scaling factors
const FONT_SCALE = {
  small: 0.85,
  default: 1,
  large: 1.25,
};

// Context type
interface SettingsContextType {
  // Theme
  themeMode: ThemeMode;
  isDarkMode: boolean;
  setThemeMode: (mode: ThemeMode) => void;
  
  // Language
  language: Language;
  setLanguage: (lang: Language) => void;
  
  // Font Size
  fontSize: FontSize;
  setFontSize: (size: FontSize) => void;
  fontScale: number;
  
  // Typography - scaled based on font size setting
  typography: ReturnType<typeof createTypography>;
  
  // Translation helper
  t: (key: string) => string;

  // Notifications
  pushNotifications: boolean;
  setPushNotifications: (value: boolean) => void;
  hapticFeedback: boolean;
  setHapticFeedback: (value: boolean) => void;
}

// Default context
const defaultSettings: SettingsContextType = {
  themeMode: 'system',
  isDarkMode: false,
  setThemeMode: () => {},
  language: 'en',
  setLanguage: () => {},
  fontSize: 'default',
  setFontSize: () => {},
  fontScale: 1,
  typography: createTypography(1),
  t: (key: string) => key,
  pushNotifications: true,
  setPushNotifications: () => {},
  hapticFeedback: false,
  setHapticFeedback: () => {},
};

// Create context
const SettingsContext = createContext<SettingsContextType>(defaultSettings);

// Use imported translations directly
const translations = i18nTranslations;

export function SettingsProvider({ children }: { children: ReactNode }) {
  const systemColorScheme = useColorScheme();
  
  // State with defaults
  const [themeMode, setThemeModeState] = useState<ThemeMode>('system');
  const [language, setLanguageState] = useState<Language>('en');
  const [fontSize, setFontSizeState] = useState<FontSize>('default');
  const [pushNotifications, setPushNotificationsState] = useState<boolean>(true);
  const [hapticFeedback, setHapticFeedbackState] = useState<boolean>(false);
  const [isLoaded, setIsLoaded] = useState(false);
  
  // Load settings from storage on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        // For now, we'll use in-memory defaults
        // AsyncStorage can be added back once installed
        console.log('Settings loaded with defaults');
      } catch (error) {
        console.error('Error loading settings:', error);
      } finally {
        setIsLoaded(true);
      }
    };
    
    loadSettings();
  }, []);
  
  // Determine actual dark mode based on theme mode and system preference
  const isDarkMode = themeMode === 'system' 
    ? systemColorScheme === 'dark'
    : themeMode === 'dark';
  
  // Theme mode setter - also updates native appearance on iOS/Android only
  const setThemeMode = useCallback(async (mode: ThemeMode) => {
    setThemeModeState(mode);
    
    // Update native color scheme only on native platforms (iOS/Android)
    // React Native Web doesn't support Appearance.setColorScheme
    if (isNativePlatform && typeof Appearance.setColorScheme === 'function') {
      if (mode === 'system') {
        Appearance.setColorScheme(null as any);
      } else {
        Appearance.setColorScheme(mode);
      }
    }
    
    try {
      // AsyncStorage can be added back once installed
    } catch (error) {
      console.error('Error saving theme mode:', error);
    }
  }, []);
  
  // Language setter
  const setLanguage = useCallback(async (lang: Language) => {
    setLanguageState(lang);
    try {
      // AsyncStorage can be added back once installed
    } catch (error) {
      console.error('Error saving language:', error);
    }
  }, []);
  
  // Font size setter
  const setFontSize = useCallback(async (size: FontSize) => {
    setFontSizeState(size);
    try {
      // AsyncStorage can be added back once installed
    } catch (error) {
      console.error('Error saving font size:', error);
    }
  }, []);

  const setPushNotifications = useCallback((value: boolean) => {
    GlobalSettings.pushNotifications = value;
    setPushNotificationsState(value);
  }, []);

  const setHapticFeedback = useCallback((value: boolean) => {
    GlobalSettings.hapticFeedback = value;
    setHapticFeedbackState(value);
  }, []);
  
  // Font scale
  const fontScale = FONT_SCALE[fontSize];
  
  // Typography based on font scale
  const typography = useMemo(() => createTypography(fontScale), [fontScale]);
  
  // Translation function - use memo to avoid recreating on every render
  const t = useCallback((key: TranslationKey): string => {
    return translations[language][key] || key;
  }, [language]);

  const value = useMemo<SettingsContextType>(() => ({
    themeMode,
    isDarkMode,
    setThemeMode,
    language,
    setLanguage,
    fontSize,
    setFontSize,
    fontScale,
    typography,
    t: t as (key: string) => string,
    pushNotifications,
    setPushNotifications,
    hapticFeedback,
    setHapticFeedback,
  }), [themeMode, isDarkMode, language, fontSize, fontScale, typography, t, pushNotifications, hapticFeedback]);
  
  if (!isLoaded) {
    return null;
  }
  
  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
}

// Hook to use settings
export function useSettings(): SettingsContextType {
  const context = useContext(SettingsContext);
  if (!context) {
    // Return default if context not available (for components outside provider)
    return defaultSettings;
  }
  return context;
}

// Helper hook for font-scaled styles
export function useFontScale() {
  const { fontScale } = useSettings();
  
  const scale = useCallback((size: number): number => {
    return Math.round(size * fontScale);
  }, [fontScale]);
  
  return { fontScale, scale };
}

export { FONT_SCALE };
