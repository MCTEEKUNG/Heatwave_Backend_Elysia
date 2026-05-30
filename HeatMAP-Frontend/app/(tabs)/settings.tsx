import { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, Alert } from 'react-native';
import { CustomSwitch } from '@/components/ui/CustomSwitch';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { Colors, DesignTokens, GlassStyle, BottomNavStyle, useResponsive } from '@/constants/theme';
import { useSettings, Language, FontSize } from '@/hooks/useSettings';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ScaledText } from '@/components/ui/ScaledText';
import * as Notifications from 'expo-notifications';
import { scheduleLocalNotification } from '@/services/NotificationService';

export default function SettingsScreen() {
  const { 
    isDarkMode, 
    setThemeMode, 
    language, 
    setLanguage, 
    fontSize, 
    setFontSize,
    typography,
    t,
    pushNotifications,
    setPushNotifications,
    hapticFeedback,
    setHapticFeedback
  } = useSettings();
  const theme = Colors[isDarkMode ? 'dark' : 'light'];
  const { isDesktop } = useResponsive();

  const handleLogout = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive' },
    ]);
  };

  const toggleDarkMode = (value: boolean) => {
    setThemeMode(value ? 'dark' : 'light');
  };

  const handleLanguageChange = (lang: Language) => {
    setLanguage(lang);
  };

  const handleFontSizeChange = (size: FontSize) => {
    setFontSize(size);
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]} edges={['top']}>
      {/* Header */}
      <View style={[
        styles.header, 
        { 
          backgroundColor: isDarkMode ? 'rgba(26, 21, 18, 0.85)' : 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(12px)'
        }
      ]}>
        <View style={styles.headerSpacer} />
        <ScaledText variant="h3" style={[styles.headerTitle, { color: theme.text }]}>{t('settingsTitle')}</ScaledText>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={[styles.scrollContent, isDesktop && styles.scrollContentDesktop]}
        showsVerticalScrollIndicator={false}
      >
        {/* Profile Section */}
        <View style={[styles.profileCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
          <View style={styles.profileContent}>
            <View style={[styles.avatar, { borderColor: `${theme.primary}30` }]}>
              <ScaledText variant="h4" style={[styles.avatarText, { color: theme.primary }]}>JD</ScaledText>
            </View>
            <View style={styles.profileInfo}>
              <ScaledText variant="h4" style={[styles.profileName, { color: theme.text }]}>John Doe</ScaledText>
              <ScaledText variant="bodySmall" style={[styles.profileEmail, { color: theme.textSecondary }]}>
                johndoe@example.com
              </ScaledText>
            </View>
          </View>
          <TouchableOpacity 
            style={[styles.editButton, { backgroundColor: theme.primary }]}
          >
            <ScaledText variant="labelLarge" style={styles.editButtonText}>{t('editProfile')}</ScaledText>
          </TouchableOpacity>
        </View>

        {/* Appearance Section - Theme Toggle */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <IconSymbol size={18} name="palette" color={theme.textSecondary} />
            <ScaledText variant="labelSmall" style={[styles.sectionTitle, { color: theme.textSecondary }]}>{t('appearance')}</ScaledText>
          </View>
          
          <View style={[styles.settingRow, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
            <View style={styles.settingLeft}>
              <IconSymbol size={20} name={isDarkMode ? 'dark_mode' : 'light_mode'} color={theme.primary} />
              <View>
                <ScaledText variant="labelLarge" style={[styles.settingLabel, { color: theme.text }]}>{t('darkMode')}</ScaledText>
                <ScaledText variant="bodySmall" style={[styles.settingDescription, { color: theme.textSecondary }]}>
                  {isDarkMode ? t('darkModeOn') : t('darkModeOff')}
                </ScaledText>
              </View>
            </View>
            <CustomSwitch
              value={isDarkMode}
              onValueChange={toggleDarkMode}
            />
          </View>
        </View>

        {/* Language Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <IconSymbol size={18} name="language" color={theme.textSecondary} />
            <ScaledText variant="labelSmall" style={[styles.sectionTitle, { color: theme.textSecondary }]}>{t('language')} / ภาษา</ScaledText>
          </View>
          
          <View style={[styles.toggleContainer, { backgroundColor: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0, 0, 0, 0.05)' }]}>
            <TouchableOpacity
              style={[
                styles.toggleOption,
                language === 'en' && [styles.toggleActive, { backgroundColor: isDarkMode ? '#3D3530' : '#fff' }]
              ]}
              onPress={() => handleLanguageChange('en')}
            >
              <ScaledText variant="labelMedium" style={[
                styles.toggleText,
                { color: language === 'en' ? theme.primary : theme.textSecondary }
              ]}>
                ENGLISH (EN)
              </ScaledText>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.toggleOption,
                language === 'th' && [styles.toggleActive, { backgroundColor: isDarkMode ? '#3D3530' : '#fff' }]
              ]}
              onPress={() => handleLanguageChange('th')}
            >
              <ScaledText variant="labelMedium" style={[
                styles.toggleText,
                { color: language === 'th' ? theme.primary : theme.textSecondary }
              ]}>
                ไทย (TH)
              </ScaledText>
            </TouchableOpacity>
          </View>
        </View>

        {/* Alert Settings Section */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <IconSymbol size={18} name="notifications" color={theme.textSecondary} />
            <ScaledText variant="labelSmall" style={[styles.sectionTitle, { color: theme.textSecondary }]}>{t('notifications')}</ScaledText>
          </View>
          
          <View style={styles.settingsList}>
            {/* Push Notifications */}
            <View style={[styles.settingRow, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
              <View style={styles.settingLeft}>
                <IconSymbol size={20} name="notifications_active" color={theme.textSecondary} />
                <ScaledText variant="labelLarge" style={[styles.settingLabel, { color: theme.text }]}>{t('pushNotifications')}</ScaledText>
              </View>
              <CustomSwitch
                value={pushNotifications}
                onValueChange={setPushNotifications}
                trackColorOff={isDarkMode ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)'}
              />
            </View>
            
            {/* Haptic Feedback */}
            <View style={[styles.settingRow, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
              <View style={styles.settingLeft}>
                <IconSymbol size={20} name="vibration" color={theme.textSecondary} />
                <ScaledText variant="labelLarge" style={[styles.settingLabel, { color: theme.text }]}>{t('hapticFeedback')}</ScaledText>
              </View>
              <CustomSwitch
                value={hapticFeedback}
                onValueChange={setHapticFeedback}
                trackColorOff={isDarkMode ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)'}
              />
            </View>

            {/* Test Notification Button */}
            <TouchableOpacity 
              style={[styles.settingRow, GlassStyle[isDarkMode ? 'dark' : 'light'], { justifyContent: 'center', backgroundColor: `${theme.primary}15` }]}
              onPress={async () => {
                if (!pushNotifications) {
                  Alert.alert("Disabled", "Push notifications are disabled in your settings.");
                  return;
                }
                await scheduleLocalNotification(
                  "🔥 Heatwave Alert Simulated", 
                  "This is a test notification from your settings.",
                  { url: "/(tabs)/alerts" }
                );
              }}
            >
              <View style={styles.settingLeft}>
                <IconSymbol size={20} name="notifications_active" color={theme.primary} />
                <ScaledText variant="labelLarge" style={[styles.settingLabel, { color: theme.primary }]}>{t('testNotification') || "Test Notification"}</ScaledText>
              </View>
            </TouchableOpacity>
            
            {/* Font Size */}
            <View style={[styles.settingRowInner, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
              <View style={styles.settingLeft}>
                <IconSymbol size={20} name="format_size" color={theme.textSecondary} />
                <View>
                  <ScaledText variant="labelLarge" style={{ color: theme.text }}>{t('fontSize')}</ScaledText>
                  <ScaledText variant="bodySmall" style={{ color: theme.textSecondary }}>
                    {fontSize === 'small' ? 'Small (85%)' : fontSize === 'default' ? 'Medium (100%)' : 'Large (125%)'}
                  </ScaledText>
                </View>
              </View>
              <View style={[styles.fontSizeContainer, { backgroundColor: isDarkMode ? 'rgba(255,255,255,0.1)' : 'rgba(0, 0, 0, 0.05)' }]}>
                {(['small', 'default', 'large'] as FontSize[]).map((size) => (
                  <TouchableOpacity
                    key={size}
                    style={[
                      styles.fontSizeOption,
                      fontSize === size && [styles.fontSizeActive, { backgroundColor: isDarkMode ? '#3D3530' : '#fff' }]
                    ]}
                    onPress={() => handleFontSizeChange(size)}
                  >
                    <ScaledText 
                      variant="labelLarge"
                      style={{ color: fontSize === size ? theme.primary : theme.textSecondary }}
                    >
                      {size === 'small' ? 'S' : size === 'default' ? 'M' : 'L'}
                    </ScaledText>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
            
            {/* Font Size Preview */}
            <View style={[styles.fontPreviewCard, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
              <ScaledText variant="labelSmall" style={{ color: theme.textSecondary, textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>Preview</ScaledText>
              <ScaledText variant="h3" style={{ color: theme.text, marginBottom: 8 }}>Heading Text</ScaledText>
              <ScaledText variant="bodyMedium" style={{ color: theme.text, marginBottom: 8 }}>Body text sample - This is how normal text appears.</ScaledText>
              <ScaledText variant="labelMedium" style={{ color: theme.textSecondary }}>Label text - Buttons and UI elements</ScaledText>
            </View>
          </View>
        </View>

        {/* Heat Alert Preferences */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <IconSymbol size={18} name="warning" color={theme.extreme} />
            <ScaledText variant="labelSmall" style={[styles.sectionTitle, { color: theme.textSecondary }]}>{t('heatAlerts')}</ScaledText>
          </View>
          
          <View style={[styles.infoCard, { backgroundColor: `${theme.warning}15`, borderColor: theme.warning }]}>
            <IconSymbol size={24} name="info" color={theme.warning} />
            <View style={styles.infoContent}>
              <ScaledText variant="labelLarge" style={[styles.infoTitle, { color: theme.text }]}>{t('heatAlerts')}</ScaledText>
              <ScaledText variant="bodySmall" style={[styles.infoText, { color: theme.textSecondary }]}>
                {t('heatAlertsInfo')}
              </ScaledText>
            </View>
          </View>
        </View>

        {/* Secondary Actions */}
        <View style={styles.actionsSection}>
          <TouchableOpacity style={[styles.actionButton, GlassStyle[isDarkMode ? 'dark' : 'light']]}>
            <ScaledText variant="labelLarge" style={[styles.actionText, { color: theme.text }]}>{t('securityPrivacy')}</ScaledText>
            <IconSymbol size={20} name="chevron_right" color={theme.textSecondary} />
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.actionButton, { backgroundColor: `${theme.primary}10` }]}
            onPress={handleLogout}
          >
            <ScaledText variant="labelLarge" style={[styles.actionText, { color: theme.primary }]}>{t('signOut')}</ScaledText>
            <IconSymbol size={20} name="logout" color={theme.primary} />
          </TouchableOpacity>
        </View>
      </ScrollView>

      {/* Bottom Navigation */}
      <View style={[
        styles.bottomNav, 
        BottomNavStyle.container,
        isDarkMode ? BottomNavStyle.dark : {}
      ]}>
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => router.push('/(tabs)/map')}
        >
          <IconSymbol size={28} name="map" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navMap')}</ScaledText>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => router.push('/(tabs)/alerts')}
        >
          <IconSymbol size={28} name="notifications" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navAlerts')}</ScaledText>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={styles.navItem}
          onPress={() => router.push('/checklist')}
        >
          <IconSymbol size={28} name="shield" color={theme.tabIconDefault} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.tabIconDefault }]}>{t('navSafety')}</ScaledText>
        </TouchableOpacity>
        
        <TouchableOpacity style={styles.navItem}>
          <IconSymbol size={28} name="person.fill" color={theme.primary} />
          <ScaledText variant="labelSmall" style={[styles.navLabel, { color: theme.primary }]}>{t('navProfile')}</ScaledText>
          <View style={[styles.activeDot, { backgroundColor: theme.primary }]} />
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: DesignTokens.spacing.lg,
    paddingVertical: DesignTokens.spacing.md,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  headerSpacer: {
    width: 40,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: DesignTokens.spacing.md,
    paddingBottom: 120,
  },
  scrollContentDesktop: {
    maxWidth: 600,
    alignSelf: 'center',
    width: '100%',
  },
  profileCard: {
    padding: DesignTokens.spacing.lg,
    borderRadius: DesignTokens.borderRadius.xl,
    marginBottom: DesignTokens.spacing.lg,
  },
  profileContent: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: DesignTokens.spacing.md,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 3,
    backgroundColor: 'rgba(0, 0, 0, 0.05)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    fontSize: 28,
    fontWeight: '700',
  },
  profileInfo: {
    flex: 1,
    marginLeft: DesignTokens.spacing.md,
  },
  profileName: {
    fontSize: 24,
    fontWeight: '700',
  },
  profileEmail: {
    fontSize: 14,
    marginTop: 4,
  },
  editButton: {
    paddingVertical: DesignTokens.spacing.sm + 2,
    paddingHorizontal: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.full,
    alignItems: 'center',
  },
  editButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  section: {
    marginBottom: DesignTokens.spacing.lg,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: DesignTokens.spacing.sm,
    marginBottom: DesignTokens.spacing.md,
    paddingHorizontal: DesignTokens.spacing.sm,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  toggleContainer: {
    flexDirection: 'row',
    borderRadius: DesignTokens.borderRadius.lg,
    padding: 4,
  },
  toggleOption: {
    flex: 1,
    paddingVertical: DesignTokens.spacing.sm + 2,
    alignItems: 'center',
    borderRadius: DesignTokens.borderRadius.md,
  },
  toggleActive: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  toggleText: {
    fontSize: 14,
    fontWeight: '600',
  },
  settingsList: {
    gap: DesignTokens.spacing.md,
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  settingRowInner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
    gap: DesignTokens.spacing.md,
  },
  settingLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: DesignTokens.spacing.md,
  },
  settingLabel: {
    fontSize: 16,
    fontWeight: '600',
  },
  settingDescription: {
    fontSize: 12,
    marginTop: 2,
  },
  fontSizeContainer: {
    flexDirection: 'row',
    borderRadius: DesignTokens.borderRadius.lg,
    padding: 4,
  },
  fontSizeOption: {
    width: 40,
    paddingVertical: DesignTokens.spacing.sm,
    alignItems: 'center',
    borderRadius: DesignTokens.borderRadius.md,
  },
  fontSizeActive: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  fontSizeText: {
    fontSize: 14,
    fontWeight: '600',
  },
  fontPreviewCard: {
    marginTop: DesignTokens.spacing.md,
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  fontPreviewTitle: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: DesignTokens.spacing.sm,
  },
  infoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
    borderWidth: 1,
    gap: DesignTokens.spacing.md,
  },
  infoContent: {
    flex: 1,
  },
  infoTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  infoText: {
    fontSize: 13,
    marginTop: 4,
    lineHeight: 18,
  },
  actionsSection: {
    gap: DesignTokens.spacing.md,
    marginTop: DesignTokens.spacing.md,
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: DesignTokens.spacing.md,
    borderRadius: DesignTokens.borderRadius.xl,
  },
  actionText: {
    fontSize: 16,
    fontWeight: '600',
  },
  bottomNav: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingHorizontal: DesignTokens.spacing.md,
  },
  navItem: {
    alignItems: 'center',
    justifyContent: 'center',
    width: 64,
    position: 'relative',
  },
  navLabel: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginTop: 4,
  },
  activeDot: {
    position: 'absolute',
    bottom: -8,
    width: 4,
    height: 4,
    borderRadius: 2,
  },
});
