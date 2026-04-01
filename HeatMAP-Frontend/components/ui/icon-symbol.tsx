// Fallback for using MaterialIcons on Android and web.

import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { SymbolWeight } from 'expo-symbols';
import { ComponentProps } from 'react';
import { OpaqueColorValue, type StyleProp, type TextStyle } from 'react-native';

type IconMapping = Record<string, string>;
type IconSymbolName = string;

/**
 * Add your SF Symbols to Material Icons mappings here.
 * Material Icons names are used to match design's Material Symbols Outlined
 */
const MAPPING: IconMapping = {
  // Navigation icons (matching design)
  'house.fill': 'home',
  'map.fill': 'map',
  'notifications': 'notifications',
  'shield.fill': 'shield',
  'person.fill': 'person',
  
  // Map related icons
  'my_location': 'my-location',
  'add': 'add',
  'remove': 'remove',
  'directions': 'directions',
  
  // Weather icons
  'sunny': 'wb-sunny',
  'cloud': 'cloud',
  'partly_cloudy_day': 'wb-cloudy',
  'partly-cloudy-day': 'wb-cloudy',
  'bedtime': 'bedtime',
  'water_drop': 'water-drop',
  'ac_unit': 'ac-unit',
  'wb_sunny': 'wb-sunny',
  
  // Alert icons
  'warning': 'warning',
  'notifications_active': 'notifications-active',
  'local_hospital': 'local-hospital',
  'phone_in_talk': 'phone-in-talk',
  
  // Theme / mode icons
  'dark_mode': 'dark-mode',
  'light_mode': 'light-mode',

  // Motion icons
  'directions_walk': 'directions-walk',

  // Settings icons
  'language': 'language',
  'vibration': 'vibration',
  'format_size': 'format-size',
  'security': 'security',
  'logout': 'logout',
  'chevron_right': 'chevron-right',
  'chevron.left.forwardslash.chevron.right': 'code',
  'arrow_back_ios_new': 'arrow-back-ios-new',
  
  // Places icons
  'local_mall': 'local-mall',
  'local_grocery_store': 'local-grocery-store',
  'storefront': 'storefront',
  'local_library': 'local-library',
  'account_balance': 'account-balance',
  'directions_transit': 'directions-transit',
  'place': 'place',
  
  // General icons
  'calendar': 'calendar-today',
  'bell.fill': 'notifications',
  'gearshape.fill': 'settings',
  'checkmark.shield.fill': 'verified-user',
  'info.fill': 'info',
  'check': 'check',
  'shield_check': 'shield',
};

/**
 * An icon component that uses native SF Symbols on iOS, and Material Icons on Android and web.
 * This ensures a consistent look across platforms, and optimal resource usage.
 * Icon `name`s are based on SF Symbols and require manual mapping to Material Icons.
 */
export function IconSymbol({
  name,
  size = 24,
  color,
  style,
}: {
  name: IconSymbolName;
  size?: number;
  color: string | OpaqueColorValue;
  style?: StyleProp<TextStyle>;
  weight?: SymbolWeight;
}) {
  const iconName = MAPPING[name] || name;
  return (
    <MaterialIcons
      color={color}
      size={size}
      name={iconName as any}
      style={style}
    />
  );
}
