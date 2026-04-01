/**
 * ScaledText Component
 * A text component that automatically scales based on user font size preference
 * Used for accessibility - applies global font scale from settings
 */

import React from 'react';
import { Text, TextProps, StyleSheet } from 'react-native';
import { useSettings } from '@/hooks/useSettings';

/**
 * Typography variant names matching the design system
 */
export type TypographyVariant = 
  | 'displayLarge'
  | 'displayMedium'
  | 'displaySmall'
  | 'h1'
  | 'h2'
  | 'h3'
  | 'h4'
  | 'bodyLarge'
  | 'bodyMedium'
  | 'bodySmall'
  | 'labelLarge'
  | 'labelMedium'
  | 'labelSmall'
  | 'caption';

interface ScaledTextProps extends TextProps {
  /** Typography variant to use */
  variant?: TypographyVariant;
  /** Direct font size override (in pixels) - will be scaled */
  fontSize?: number;
  /** Children content */
  children?: React.ReactNode;
}

/**
 * ScaledText - Text component that respects user font size settings
 * 
 * Usage:
 * <ScaledText variant="h1">Heading</ScaledText>
 * <ScaledText fontSize={16}>Custom size</ScaledText>
 * <ScaledText>Default body text</ScaledText>
 */
export function ScaledText({ 
  variant, 
  fontSize, 
  style, 
  children, 
  ...props 
}: ScaledTextProps) {
  const { typography, fontScale } = useSettings();
  
  // Calculate the scaled style
  const getStyle = () => {
    // If variant is specified, use typography
    if (variant && typography[variant]) {
      return typography[variant];
    }
    
    // If fontSize is specified, apply scaling
    if (fontSize) {
      const scaledSize = Math.round(fontSize * fontScale);
      return {
        fontSize: scaledSize,
        lineHeight: Math.round(scaledSize * 1.5),
      };
    }
    
    // Default to bodyMedium
    return typography.bodyMedium;
  };
  
  return (
    <Text style={[getStyle(), style]} {...props}>
      {children}
    </Text>
  );
}

export default ScaledText;
