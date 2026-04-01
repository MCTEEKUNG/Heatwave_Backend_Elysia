/**
 * Heatwave Forecast App Theme
 * Warm Minimal Theme - Modern & Minimal Design
 * Primary: #E67E22 (Carrot Orange)
 * Background Light: #FAFAFA
 * Background Dark: #1A1A1A
 * Accent: #F5F5F5
 * Glassmorphism design system
 */

import { Platform, Dimensions, useWindowDimensions, Text, TextStyle } from 'react-native';

// Design tokens from Stitch design - Heat themed
export const DesignTokens = {
  // Warm Minimal primary colors
  primaryColor: '#E67E22',      // Carrot Orange - warm minimal
  secondaryColor: '#2C3E50',      // Dark slate - neutral secondary
  accentColor: '#F5F5F5',        // Light gray - minimal accent
  
  // Severity colors (heat-themed)
  severityColors: {
    extreme: '#EF4444',  // Red - danger/heat warning
    medium: '#FFA500',   // Orange - heat caution
    low: '#22C55E',      // Green - safe/cool
  },
  
  // iOS colors
  iosBlue: '#007AFF',
  iosGray: '#8E8E93',
  
  // Background gradient colors
  backgroundGradient: {
    light: ['#FAFAFA', '#F0F0F0'],  // Clean light backgrounds
    dark: ['#1A1A1A', '#0D0D0D'],    // Deep dark backgrounds
  },
  
  // Surface colors
  surfaceColor: 'rgba(255, 255, 255, 0.95)',
  glassColor: 'rgba(255, 255, 255, 0.75)',
  glassBorder: 'rgba(255, 255, 255, 0.4)',
  glassDark: 'rgba(26, 26, 26, 0.85)',
  glassBorderDark: 'rgba(255, 255, 255, 0.15)',
  
  // Text colors - improved contrast
  textPrimary: '#1A1A1A',        // Near black for high contrast
  textSecondary: '#4A4A4A',      // Dark gray
  textPrimaryDark: '#F5F5F5',    // Near white
  textSecondaryDark: '#A0A0A0', // Light gray
  
  // Border colors
  borderColor: 'rgba(0, 0, 0, 0.12)',
  borderColorDark: 'rgba(255, 255, 255, 0.15)',
  
  // Error/Alert colors
  errorColor: '#EF4444',
  warningColor: '#FFA500',
  successColor: '#22C55E',
  
  // Glassmorphism
  glass: {
    backgroundColor: 'rgba(255, 255, 255, 0.75)',
    borderColor: 'rgba(255, 255, 255, 0.4)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 24,
    elevation: 12,
  },
  
  // Spacing based on 8px grid - standardized
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
  },
  
  // Border radius
  borderRadius: {
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
    xxl: 32,
    full: 9999,
  },
};

// Responsive breakpoints
export const Breakpoints = {
  sm: 480,
  md: 768,
  lg: 1024,
  xl: 1280,
};

// Hook for responsive design
export function useResponsive() {
  const { width, height } = useWindowDimensions();
  const isSmall = width < Breakpoints.sm;
  const isMobile = width < Breakpoints.md;
  const isTablet = width >= Breakpoints.md && width < Breakpoints.lg;
  const isDesktop = width >= Breakpoints.lg;
  
  return {
    width,
    height,
    isSmall,
    isMobile,
    isTablet,
    isDesktop,
    isLandscape: width > height,
  };
}

const tintColorLight = DesignTokens.primaryColor;
const tintColorDark = '#FF6B35'; // Primary orange for dark mode

export const Colors = {
  light: {
    // Primary theme
    text: DesignTokens.textPrimary,
    textSecondary: DesignTokens.textSecondary,
    textMuted: '#6B6B6B',
    background: '#FAFAFA',
    surface: DesignTokens.surfaceColor,
    glass: DesignTokens.glass.backgroundColor,
    tint: tintColorLight,
    icon: '#5A5A5A',
    tabIconDefault: '#8A8A8A',
    tabIconSelected: tintColorLight,
    primary: DesignTokens.primaryColor,
    secondary: DesignTokens.secondaryColor,
    accent: DesignTokens.accentColor,
    border: DesignTokens.borderColor,
    
    // Severity colors
    extreme: DesignTokens.severityColors.extreme,
    medium: DesignTokens.severityColors.medium,
    low: DesignTokens.severityColors.low,
    
    // Status colors
    error: DesignTokens.errorColor,
    warning: DesignTokens.warningColor,
    success: DesignTokens.successColor,
    
    // iOS colors
    iosBlue: DesignTokens.iosBlue,
    iosGray: DesignTokens.iosGray,
    
    // Additional
    backdrop: 'rgba(0, 0, 0, 0.4)',
    overlay: 'rgba(255, 255, 255, 0.9)',
  },
  dark: {
    // Primary theme - high contrast
    text: DesignTokens.textPrimaryDark,
    textSecondary: DesignTokens.textSecondaryDark,
    textMuted: '#808080',
    background: '#1A1A1A',
    surface: 'rgba(40, 40, 40, 0.95)',
    glass: DesignTokens.glassDark,
    tint: tintColorDark,
    icon: '#C0C0C0',
    tabIconDefault: '#8A8A8A',
    tabIconSelected: tintColorDark,
    primary: tintColorDark,
    secondary: DesignTokens.secondaryColor,
    accent: DesignTokens.accentColor,
    border: DesignTokens.borderColorDark,
    
    // Severity colors
    extreme: '#FF6B6B',  // Lighter red for dark mode
    medium: '#FFB84D',   // Lighter orange for dark mode
    low: '#4ADE80',      // Lighter green for dark mode
    
    // Status colors
    error: '#FF6B6B',
    warning: '#FFB84D',
    success: '#4ADE80',
    
    // iOS colors
    iosBlue: DesignTokens.iosBlue,
    iosGray: DesignTokens.iosGray,
    
    // Additional
    backdrop: 'rgba(0, 0, 0, 0.6)',
    overlay: 'rgba(30, 25, 22, 0.95)',
  },
};

export const Fonts = Platform.select({
  ios: {
    sans: 'System',
    serif: 'Georgia',
    rounded: 'System',
    mono: 'Menlo',
    display: 'Space Grotesk',
  },
  android: {
    sans: 'Roboto',
    serif: 'serif',
    rounded: 'sans-serif-medium',
    mono: 'monospace',
    display: 'sans-serif-medium',
  },
  default: {
    sans: 'system-ui',
    serif: 'serif',
    rounded: 'sans-serif',
    mono: 'monospace',
    display: 'system-ui',
  },
  web: {
    sans: "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    display: "'Space Grotesk', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    serif: "Georgia, 'Times New Roman', serif",
    rounded: "'Inter', sans-serif",
    mono: "SFMono-Regular, Menlo, Monaco, Consolas, monospace",
  },
});

// Font size scaling factors
export const FONT_SIZE_SCALE = {
  small: 0.85,
  default: 1,
  large: 1.25,
};

// Base font sizes (in pixels)
export const BASE_FONT_SIZES = {
  // Display / Headings
  displayLarge: 38,
  displayMedium: 32,
  displaySmall: 28,
  
  // Headings
  heading1: 24,
  heading2: 22,
  heading3: 20,
  heading4: 18,
  
  // Body
  bodyLarge: 18,
  bodyMedium: 16,
  bodySmall: 14,
  
  // Labels / UI
  labelLarge: 16,
  labelMedium: 14,
  labelSmall: 12,
  
  // Caption
  caption: 11,
};

// Typography sizes based on scale factor
export function getScaledFontSize(baseSize: number, scale: number = 1): number {
  return Math.round(baseSize * scale);
}

// Create scaled typography object
export function createTypography(scale: number = 1) {
  return {
    // Display
    displayLarge: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.displayLarge, scale),
      fontWeight: '700' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.displayLarge, scale) * 1.2,
    },
    displayMedium: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.displayMedium, scale),
      fontWeight: '700' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.displayMedium, scale) * 1.2,
    },
    displaySmall: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.displaySmall, scale),
      fontWeight: '600' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.displaySmall, scale) * 1.2,
    },
    
    // Headings
    h1: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.heading1, scale),
      fontWeight: '700' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.heading1, scale) * 1.3,
    },
    h2: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.heading2, scale),
      fontWeight: '600' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.heading2, scale) * 1.3,
    },
    h3: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.heading3, scale),
      fontWeight: '600' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.heading3, scale) * 1.3,
    },
    h4: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.heading4, scale),
      fontWeight: '600' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.heading4, scale) * 1.3,
    },
    
    // Body
    bodyLarge: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.bodyLarge, scale),
      fontWeight: '400' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.bodyLarge, scale) * 1.5,
    },
    bodyMedium: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.bodyMedium, scale),
      fontWeight: '400' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.bodyMedium, scale) * 1.5,
    },
    bodySmall: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.bodySmall, scale),
      fontWeight: '400' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.bodySmall, scale) * 1.5,
    },
    
    // Labels
    labelLarge: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.labelLarge, scale),
      fontWeight: '600' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.labelLarge, scale) * 1.4,
    },
    labelMedium: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.labelMedium, scale),
      fontWeight: '500' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.labelMedium, scale) * 1.4,
    },
    labelSmall: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.labelSmall, scale),
      fontWeight: '500' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.labelSmall, scale) * 1.4,
    },
    
    // Caption
    caption: {
      fontSize: getScaledFontSize(BASE_FONT_SIZES.caption, scale),
      fontWeight: '400' as TextStyle['fontWeight'],
      lineHeight: getScaledFontSize(BASE_FONT_SIZES.caption, scale) * 1.4,
    },
  };
}

// Glassmorphism style helper
export const GlassStyle = {
  light: {
    backgroundColor: 'rgba(255, 255, 255, 0.75)',
    borderColor: 'rgba(255, 255, 255, 0.4)',
    borderWidth: 1,
    borderRadius: DesignTokens.borderRadius.xl,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 24,
    elevation: 12,
  },
  dark: {
    backgroundColor: 'rgba(45, 36, 32, 0.85)',
    borderColor: 'rgba(255, 255, 255, 0.15)',
    borderWidth: 1,
    borderRadius: DesignTokens.borderRadius.xl,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 24,
    elevation: 12,
  },
};

// Soft shadow style
export const SoftShadow = {
  light: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.15,
    shadowRadius: 40,
    elevation: 12,
  },
  dark: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.4,
    shadowRadius: 40,
    elevation: 12,
  },
};

// Bottom navigation style
export const BottomNavStyle = {
  container: {
    position: 'absolute' as const,
    bottom: 24,
    left: 24,
    right: 24,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    backdropFilter: 'blur(20px)' as any,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.4)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 32,
    elevation: 12,
  },
  dark: {
    backgroundColor: 'rgba(30, 25, 22, 0.85)',
    borderColor: 'rgba(255, 255, 255, 0.15)',
  },
};

// Header style
export const HeaderStyle = {
  container: {
    paddingHorizontal: 24,
    paddingVertical: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.85)',
    backdropFilter: 'blur(12px)' as any,
    borderBottomWidth: 0,
  },
  dark: {
    backgroundColor: 'rgba(26, 21, 18, 0.85)',
  },
};

// Card style
export const CardStyle = {
  light: {
    backgroundColor: '#FFFFFF',
    borderRadius: DesignTokens.borderRadius.xl,
    padding: DesignTokens.spacing.lg,
    borderWidth: 1,
    borderColor: 'rgba(0, 0, 0, 0.06)',
    ...SoftShadow.light,
  },
  dark: {
    backgroundColor: 'rgba(45, 36, 32, 0.95)',
    borderRadius: DesignTokens.borderRadius.xl,
    padding: DesignTokens.spacing.lg,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    ...SoftShadow.dark,
  },
};

// Button styles
export const ButtonStyle = {
  primary: {
    backgroundColor: DesignTokens.primaryColor,
    borderRadius: DesignTokens.borderRadius.lg,
    paddingVertical: DesignTokens.spacing.md,
    paddingHorizontal: DesignTokens.spacing.lg,
  },
  secondary: {
    backgroundColor: 'transparent',
    borderWidth: 2,
    borderColor: DesignTokens.primaryColor,
    borderRadius: DesignTokens.borderRadius.lg,
    paddingVertical: DesignTokens.spacing.md,
    paddingHorizontal: DesignTokens.spacing.lg,
  },
  danger: {
    backgroundColor: DesignTokens.severityColors.extreme,
    borderRadius: DesignTokens.borderRadius.lg,
    paddingVertical: DesignTokens.spacing.md,
    paddingHorizontal: DesignTokens.spacing.lg,
  },
};
