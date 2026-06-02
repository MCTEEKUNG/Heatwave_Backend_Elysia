/**
 * ProvinceSelector
 *
 * A compact button that opens a searchable modal list of the 77 Thai
 * provinces. Province names follow the active app language (TH/EN).
 *
 * Used on the Map screen to drive `useProvinceForecast(provinceId)`.
 */

import React, { useMemo, useState } from 'react';
import {
  View,
  Text,
  Modal,
  TextInput,
  FlatList,
  Pressable,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { Colors, DesignTokens } from '@/constants/theme';
import { useSettings } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import type { Province } from '@/services/provincesService';

interface Props {
  provinces: Province[];
  selected: Province | null;
  onSelect: (province: Province) => void;
  loading?: boolean;
}

export function ProvinceSelector({ provinces, selected, onSelect, loading }: Props) {
  const { isDarkMode, language, t } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const label = (p: Province) => (language === 'th' ? p.name_th : p.name_en);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return provinces;
    return provinces.filter(
      (p) =>
        p.name_en.toLowerCase().includes(q) ||
        p.name_th.toLowerCase().includes(q) ||
        p.code.toLowerCase().includes(q),
    );
  }, [provinces, query]);

  const close = () => {
    setOpen(false);
    setQuery('');
  };

  return (
    <>
      <TouchableOpacity
        style={[styles.trigger, { backgroundColor: theme.surface, borderColor: theme.border }]}
        onPress={() => setOpen(true)}
        activeOpacity={0.8}
        accessibilityRole="button"
        accessibilityLabel={t('selectProvince')}
      >
        <IconSymbol size={18} name="map.fill" color={theme.primary} />
        <Text style={[styles.triggerText, { color: theme.text }]} numberOfLines={1}>
          {selected ? label(selected) : loading ? t('loading') : t('selectProvince')}
        </Text>
        <IconSymbol size={18} name="chevron.right" color={theme.textSecondary} />
      </TouchableOpacity>

      <Modal visible={open} animationType="slide" transparent onRequestClose={close}>
        <Pressable style={styles.backdrop} onPress={close}>
          <Pressable
            style={[styles.sheet, { backgroundColor: theme.background }]}
            onPress={(e) => e.stopPropagation()}
          >
            <View style={styles.sheetHeader}>
              <Text style={[styles.sheetTitle, { color: theme.text }]}>{t('selectProvince')}</Text>
              <TouchableOpacity onPress={close} accessibilityLabel={t('close')}>
                <IconSymbol size={24} name="xmark" color={theme.textSecondary} />
              </TouchableOpacity>
            </View>

            <View style={[styles.searchBox, { backgroundColor: theme.surface, borderColor: theme.border }]}>
              <IconSymbol size={18} name="magnifyingglass" color={theme.textSecondary} />
              <TextInput
                style={[styles.searchInput, { color: theme.text }]}
                placeholder={t('searchProvince')}
                placeholderTextColor={theme.textMuted}
                value={query}
                onChangeText={setQuery}
                autoCorrect={false}
              />
            </View>

            <FlatList
              data={filtered}
              keyExtractor={(item) => String(item.id)}
              keyboardShouldPersistTaps="handled"
              style={styles.list}
              renderItem={({ item }) => {
                const isSel = selected?.id === item.id;
                return (
                  <TouchableOpacity
                    style={[styles.row, isSel && { backgroundColor: `${theme.primary}1A` }]}
                    onPress={() => {
                      onSelect(item);
                      close();
                    }}
                  >
                    <View style={styles.rowText}>
                      <Text style={[styles.rowName, { color: theme.text }]}>{label(item)}</Text>
                      <Text style={[styles.rowSub, { color: theme.textMuted }]}>
                        {language === 'th' ? item.name_en : item.name_th} · {item.region}
                      </Text>
                    </View>
                    {isSel && <IconSymbol size={20} name="checkmark" color={theme.primary} />}
                  </TouchableOpacity>
                );
              }}
              ListEmptyComponent={
                <Text style={[styles.empty, { color: theme.textMuted }]}>{t('noResults')}</Text>
              }
            />
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

export default ProvinceSelector;

const styles = StyleSheet.create({
  trigger: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: DesignTokens.spacing.sm,
    paddingVertical: 10,
    paddingHorizontal: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.full,
    borderWidth: 1,
  },
  triggerText: { flex: 1, fontSize: 14, fontWeight: '600' },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    maxHeight: '80%',
    borderTopLeftRadius: DesignTokens.borderRadius.xl,
    borderTopRightRadius: DesignTokens.borderRadius.xl,
    padding: DesignTokens.spacing.lg,
    gap: DesignTokens.spacing.md,
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sheetTitle: { fontSize: 18, fontWeight: '700' },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: DesignTokens.spacing.sm,
    paddingHorizontal: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.md,
    borderWidth: 1,
  },
  searchInput: { flex: 1, paddingVertical: 10, fontSize: 14 },
  list: { flexGrow: 0 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    paddingHorizontal: DesignTokens.spacing.sm,
    borderRadius: DesignTokens.borderRadius.md,
  },
  rowText: { flex: 1 },
  rowName: { fontSize: 15, fontWeight: '600' },
  rowSub: { fontSize: 12, marginTop: 2 },
  empty: { textAlign: 'center', paddingVertical: 24, fontSize: 14 },
});
