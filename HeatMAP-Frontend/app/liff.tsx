/**
 * /liff — LINE LIFF entry route (spec §7.5 / Phase 5)
 *
 * Opened inside the LINE app as the LIFF app URL. It lightly detects the LIFF
 * runtime: if the `@line/liff` SDK is installed it initializes with
 * EXPO_PUBLIC_LIFF_ID and reads the user profile; if the SDK is NOT installed
 * (current state — it's an optional dependency), it gracefully no-ops and just
 * renders the same province forecast view used on the web/map, so the page
 * works identically in and out of LINE.
 *
 * Data shown here is the SAME data as the Map/forecast screens (consistency).
 */

import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { Colors, DesignTokens } from '@/constants/theme';
import { useSettings } from '@/hooks/useSettings';
import { ProvinceSelector } from '@/components/ProvinceSelector';
import { ProvinceForecastPanel } from '@/components/forecast/ProvinceForecastPanel';
import { getProvinces, type Province } from '@/services/provincesService';

const LIFF_ID = process.env.EXPO_PUBLIC_LIFF_ID ?? '';

type LiffState =
  | { status: 'idle' }
  | { status: 'unavailable' }      // SDK not installed / not in LINE
  | { status: 'ready'; displayName: string | null };

/**
 * Best-effort LIFF initialization. Uses a dynamic require so the bundle does
 * not hard-depend on `@line/liff`. Any failure (SDK missing, not in LINE,
 * init error) resolves to "unavailable" and the page still renders.
 */
async function initLiff(): Promise<LiffState> {
  if (!LIFF_ID) return { status: 'unavailable' };
  try {
    // Optional dependency. The specifier is held in a variable so the bundler
    // (Metro) cannot statically resolve it — when `@line/liff` is not installed
    // the require throws at runtime and we fall through to "unavailable" instead
    // of failing the web build.
    const pkg = '@line/liff';
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod: any = require(pkg);
    const liff = mod?.default ?? mod;
    if (!liff?.init) return { status: 'unavailable' };

    await liff.init({ liffId: LIFF_ID });

    let displayName: string | null = null;
    if (liff.isLoggedIn?.()) {
      try {
        const profile = await liff.getProfile();
        displayName = profile?.displayName ?? null;
      } catch {
        // profile is optional — ignore
      }
    }
    return { status: 'ready', displayName };
  } catch {
    return { status: 'unavailable' };
  }
}

export default function LiffScreen() {
  const { isDarkMode, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];

  const [liff, setLiff] = useState<LiffState>({ status: 'idle' });
  const [provinces, setProvinces] = useState<Province[]>([]);
  const [provincesLoading, setProvincesLoading] = useState(true);
  const [selected, setSelected] = useState<Province | null>(null);

  // Init LIFF (no-op when SDK/ID absent)
  useEffect(() => {
    let active = true;
    initLiff().then((s) => {
      if (active) setLiff(s);
    });
    return () => {
      active = false;
    };
  }, []);

  // Load provinces (same source as the map screen)
  useEffect(() => {
    let active = true;
    (async () => {
      setProvincesLoading(true);
      const { provinces: list } = await getProvinces();
      if (!active) return;
      setProvinces(list);
      setProvincesLoading(false);
    })();
    return () => {
      active = false;
    };
  }, []);

  const greeting = useMemo(() => {
    if (liff.status === 'ready' && liff.displayName) return liff.displayName;
    return null;
  }, [liff]);

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: theme.background }]}
      contentContainerStyle={styles.content}
    >
      <View style={styles.header}>
        <Text style={[styles.title, { color: theme.text }]}>{t('provinceForecastTitle')}</Text>
        {greeting && (
          <Text style={[styles.subtitle, { color: theme.textMuted }]}>{greeting}</Text>
        )}
      </View>

      <ProvinceSelector
        provinces={provinces}
        selected={selected}
        onSelect={setSelected}
        loading={provincesLoading}
      />

      {provincesLoading && !selected && (
        <View style={styles.stateBox}>
          <ActivityIndicator color={theme.primary} />
        </View>
      )}

      {selected && <ProvinceForecastPanel province={selected} />}

      {!selected && !provincesLoading && (
        <Text style={[styles.hint, { color: theme.textMuted }]}>{t('selectProvince')}</Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: DesignTokens.spacing.lg, gap: DesignTokens.spacing.md, paddingTop: 48 },
  header: { gap: 4 },
  title: { fontSize: 24, fontWeight: '700' },
  subtitle: { fontSize: 14 },
  stateBox: { paddingVertical: 24, alignItems: 'center' },
  hint: { textAlign: 'center', paddingVertical: 16, fontSize: 14 },
});
