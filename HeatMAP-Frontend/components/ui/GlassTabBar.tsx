import { Platform, Pressable, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
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
  // No login concept in this app — the 4th tab is Settings + model transparency,
  // not a user profile (everyone receives the same public information).
  { key: 'profile', icon: 'settings', labelKey: 'navSettings', route: '/(tabs)/settings' },
];

const SLOT_PCT = 100 / TABS.length;

/**
 * Floating liquid-glass tab bar (Calm Authority): one shared pill nav used by
 * all four screens. The navy pill sits behind the active tab; the active
 * icon/label render white on navy, inactive stay soft navy. Web gets a real
 * backdrop blur (BottomNavStyle); native falls back to a near-opaque surface.
 *
 * NOTE — the pill is positioned with PERCENTAGES, deliberately not animated:
 * every screen renders its own GlassTabBar instance, so a mount-time spring
 * made the pill "fly in" from slot 0 on every navigation (and overshoot off
 * the bar entirely on wide/resized viewports). Static placement is correct
 * here; press feedback comes from the Pressable opacity instead.
 */
export function GlassTabBar({ active }: { active: TabKey }) {
  const { isDarkMode, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];
  const activeIndex = Math.max(0, TABS.findIndex((tab) => tab.key === active));

  const onPress = (tab: (typeof TABS)[number]) => {
    if (tab.key === active) return;
    if (Platform.OS !== 'web') {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    }
    router.push(tab.route as never);
  };

  return (
    <View style={[BottomNavStyle.container, isDarkMode ? BottomNavStyle.dark : null, styles.bar]}>
      <View style={styles.inner}>
        <View
          pointerEvents="none"
          style={[
            styles.pill,
            {
              left: `${activeIndex * SLOT_PCT}%`,
              width: `${SLOT_PCT}%`,
              backgroundColor: theme.primary,
            },
          ]}
        />
        {TABS.map((tab) => {
          const isActive = tab.key === active;
          const color = isActive ? '#FFFFFF' : theme.tabIconDefault;
          return (
            <Pressable
              key={tab.key}
              style={({ pressed }) => [styles.item, pressed && !isActive && styles.itemPressed]}
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
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    paddingHorizontal: 6,
    paddingVertical: 6,
    zIndex: 40,
  },
  inner: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'stretch',
    position: 'relative',
  },
  pill: {
    position: 'absolute',
    top: 0,
    bottom: 0,
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
  itemPressed: {
    opacity: 0.55,
  },
  label: {
    fontSize: 10,
    fontFamily: FontFamily.bodySemi,
    fontWeight: '600',
  },
});
