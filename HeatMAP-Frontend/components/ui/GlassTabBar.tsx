import { useEffect, useState } from 'react';
import { Platform, Pressable, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

import { BottomNavStyle, Colors, FontFamily } from '@/constants/theme';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ScaledText } from '@/components/ui/ScaledText';
import { useSettings } from '@/hooks/useSettings';

export type TabKey = 'map' | 'alerts' | 'safety' | 'profile';

const TABS: { key: TabKey; icon: string; labelKey: string; route: string }[] = [
  { key: 'map', icon: 'map.fill', labelKey: 'navMap', route: '/(tabs)/map' },
  { key: 'alerts', icon: 'notifications', labelKey: 'navAlerts', route: '/(tabs)/alerts' },
  { key: 'safety', icon: 'shield.fill', labelKey: 'navSafety', route: '/checklist' },
  { key: 'profile', icon: 'person.fill', labelKey: 'navProfile', route: '/(tabs)/settings' },
];

const PAD = 6; // inner padding around the sliding pill

/**
 * Floating liquid-glass tab bar (Calm Authority): one shared pill nav used by
 * all four screens. A navy "liquid" pill springs to the active tab; the active
 * icon/label render white on navy (high contrast), inactive stay soft navy.
 * Web gets a real backdrop blur (BottomNavStyle); native falls back to a
 * near-opaque surface.
 */
export function GlassTabBar({ active }: { active: TabKey }) {
  const { isDarkMode, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];
  const [barWidth, setBarWidth] = useState(0);

  const itemWidth = barWidth > 0 ? (barWidth - PAD * 2) / TABS.length : 0;
  const activeIndex = TABS.findIndex((tab) => tab.key === active);
  const pillX = useSharedValue(0);

  useEffect(() => {
    if (itemWidth > 0) {
      pillX.value = withSpring(activeIndex * itemWidth, { damping: 18, stiffness: 160 });
    }
  }, [activeIndex, itemWidth, pillX]);

  const pillStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: pillX.value }],
  }));

  const onPress = (tab: (typeof TABS)[number]) => {
    if (tab.key === active) return;
    if (Platform.OS !== 'web') {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    }
    router.push(tab.route as never);
  };

  return (
    <View
      style={[BottomNavStyle.container, isDarkMode ? BottomNavStyle.dark : null, styles.bar]}
      onLayout={(e) => setBarWidth(e.nativeEvent.layout.width)}
    >
      {itemWidth > 0 && (
        <Animated.View
          style={[
            styles.pill,
            { width: itemWidth, backgroundColor: theme.primary },
            pillStyle,
          ]}
        />
      )}
      {TABS.map((tab) => {
        const isActive = tab.key === active;
        const color = isActive ? '#FFFFFF' : theme.tabIconDefault;
        return (
          <Pressable
            key={tab.key}
            style={styles.item}
            onPress={() => onPress(tab)}
            accessibilityRole="tab"
            accessibilityState={{ selected: isActive }}
            accessibilityLabel={t(tab.labelKey)}
          >
            <IconSymbol size={22} name={tab.icon as never} color={color} />
            <ScaledText variant="labelSmall" style={[styles.label, { color }]}>
              {t(tab.labelKey)}
            </ScaledText>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    alignItems: 'stretch',
    paddingHorizontal: PAD,
    paddingVertical: PAD,
    zIndex: 40,
  },
  pill: {
    position: 'absolute',
    top: PAD,
    bottom: PAD,
    left: PAD,
    borderRadius: 999,
    shadowColor: '#16324F',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.38,
    shadowRadius: 14,
    elevation: 6,
  },
  item: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
    minHeight: 44,
  },
  label: {
    fontSize: 10,
    fontFamily: FontFamily.bodySemi,
    fontWeight: '600',
  },
});
