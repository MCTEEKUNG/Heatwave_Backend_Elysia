# Project Context – Heatwave Forecast Web Application

## 1. Project Overview

This project is a **Heatwave Forecast Web Application** designed to provide users with clear, accessible, and actionable heatwave predictions.

The system integrates AI-based forecasting trained on latitude–longitude grid datasets and presents the data in a structured and user-friendly interface.

The goal is to improve public awareness and disaster preparedness, with potential integration into LINE Official Account (LINE OA) for real-world notification distribution.

---

## 2. Core Objectives

- Provide heatwave severity forecasts in a clear calendar-based interface.
- Use a grid-based visualization (latitude–longitude blocks), not radial heatmaps.
- Apply severity-based color classification:
  - Extreme → Red (#EF4444)
  - Medium → Orange (#FFA500)
  - Low → Green (#22C55E)
- Display dynamic alerts and guide users to safety information when needed.
- Support both Light and Dark mode themes.
- Support accessibility with adjustable font sizes (Small/Medium/Large).

---

## 3. System Architecture Overview

### Frontend

- **React Native + Expo** framework for cross-platform support (Web & Native)
- **Expo Router** for file-based navigation and tabs
- **OpenStreetMap (OSM)** with `react-leaflet` for map visualization
- **Leaflet** for interactive web maps with grid overlays
- **AsyncStorage** for persistent state (Settings & Safety Checklist progress)
- **Design System** with glassmorphism, Space Grotesk font, heat-themed primary color (#FF6B35)
- Calendar-focused forecast visualization
- Grid-based map overlay (latitude–longitude blocks)
- Conditional UI components (e.g., Emergency 911 CTA, Safety Checklist buttons)

### Backend (Future)

- AI model trained on latitude–longitude grid datasets
- Forecast severity classification
- Probability-based prediction logic

### Current Implementation Status

✅ Map page with OSM and grid overlay (Thailand-wide coverage)
✅ Mock prediction data simulating AI backend
✅ Light/Dark mode with theme toggle in Settings
✅ Responsive design for mobile, tablet, and desktop
✅ Font size accessibility (S/M/L) - fully functional across all screens

---

## 4. UX/UI Principles

- Fully aligned with the heatwave-themed design system.
- Seamless transitions between components.
- Smooth animations, fluid glassmorphism cards, and cohesive interaction flows.
- Consistent theme across all pages, strictly using the **Space Grotesk** font for headings/display, precise border radii, and soft shadow projections.
- Scalable design for future feature expansion.
- Light and Dark mode support with system-aware defaults.
- Accessibility-first with adjustable font sizes.

---

## 5. Folder Structure

```
my-app/
├── app/                          # Expo Router pages
│   ├── (tabs)/                   # Tab-based navigation
│   │   ├── index.tsx            # Safety Checklist screen
│   │   ├── map.tsx              # Map screen with grid overlay
│   │   ├── alerts.tsx           # Alerts & Forecast screen
│   │   ├── settings.tsx         # Settings & Profile screen
│   │   └── _layout.tsx          # Tab layout
│   ├── _layout.tsx              # Root layout with SettingsProvider
│   ├── checklist.tsx            # Detailed checklist
│   └── global.css               # Global styles & Leaflet CSS
├── components/
│   ├── map/
│   │   ├── MapGrid.tsx          # OSM map with grid overlay
│   │   └── index.ts             # Map exports
│   └── ui/
│       ├── ScaledText.tsx       # Typography component (font scaling)
│       ├── icon-symbol.tsx      # Icon component
│       └── ...
├── constants/
│   └── theme.ts                 # Theme system & typography
├── hooks/
│   ├── useSettings.tsx          # Global settings (theme, language, font)
│   ├── useLocation.ts          # Location services
│   └── use-color-scheme.ts     # Color scheme detection
├── i18n/
│   └── translations.ts          # English & Thai translations
└── services/
    └── nearbyPlaces.ts          # Nearby services API
```

---

## 6. Global State Management

### Settings Context (`useSettings.tsx`)

The app uses React Context for global state management:

```tsx
const {
  isDarkMode, // boolean - current dark mode state
  themeMode, // 'light' | 'dark' | 'system'
  setThemeMode, // function to change theme
  language, // 'en' | 'th'
  setLanguage, // function to change language
  fontSize, // 'small' | 'default' | 'large'
  setFontSize, // function to change font size
  fontScale, // number (0.85, 1, or 1.25)
  typography, // scaled typography object
  t, // translation function
} = useSettings();
```

### Theme System (`theme.ts`)

The theme system provides:

- **Colors**: Light and dark color palettes
- **Typography**: Scaled font sizes for accessibility
- **GlassStyle**: Glassmorphism card styles
- **DesignTokens**: Spacing, border radius, etc.

---

## 7. Features

### Dark/Light Mode

- Toggle in Settings page
- Persists across app sessions
- Full coverage: backgrounds, cards, buttons, text, icons
- Map switches to dark tiles (CartoDB Dark Matter)

### Language Support

- English (en) - Default
- Thai (th)
- All UI strings translated
- Dynamic switching without restart

### Font Size Accessibility

Three options:

- **S (Small)**: 85% scale
- **M (Medium)**: 100% scale (default)
- **L (Large)**: 125% scale (for elderly users)

Implemented via `ScaledText` component:

```tsx
<ScaledText variant="h1">Heading</ScaledText>
<ScaledText variant="bodyMedium">Body text</ScaledText>
```

### Map & Grid System

- **Coverage**: Full Thailand (5.6°N to 20.5°N, 97.3°E to 105.6°E)
- **Cell Size**: 0.5 degrees (configurable)
- **Grid**: ~510 vector polygons covering entire country
- **Dark Mode**: Switches to CartoDB Dark Matter tiles

### Grid Cell Data Structure

```typescript
interface GridCell {
  id: string;
  north;
  south;
  east;
  west: number; // Bounding box
  centerLat;
  centerLng: number; // Center point
  severity: "extreme" | "medium" | "low";
  temperature: number;
  probability: number; // AI confidence (0-100)
  timestamp: string;
  gridRow;
  gridCol: number; // Grid position
}
```

---

## 8. Visualization Rules

⚠️ Important:
The system does NOT use circular heatmap overlays.

Instead:

- Each forecast corresponds to a rectangular latitude–longitude grid cell.
- UI must display square/rectangular grid overlays aligned to coordinate boundaries.
- Grid cells use vector polygons (not blurred/radius effects)

### Map Grid Implementation

- **Grid Size**: Full Thailand coverage (~30x17 cells at 0.5° resolution)
- **Cell Geometry**: Square polygons using lat/lng bounding boxes
- **Data Structure**:
  - `north`, `south`, `east`, `west` - coordinate boundaries
  - `centerLat`, `centerLng` - cell center point
  - `severity` - 'extreme' | 'medium' | 'low'
  - `temperature` - predicted temperature
  - `probability` - confidence percentage (0-100)
  - `timestamp` - prediction timestamp

---

## 9. Color Palette

### Light Mode

- **Primary**: #FF6B35 (Warm Orange - heat theme)
- **Secondary**: #FF4444 (Red for danger)
- **Background**: #FFF8F5 (Warm off-white)
- **Text Primary**: #1A1A1A (High contrast)
- **Text Secondary**: #4A4A4A

### Dark Mode

- **Primary**: #FF8C5A (Lighter orange for dark backgrounds)
- **Secondary**: #FF6B6B (Lighter red)
- **Background**: #1A1512 (Dark warm)
- **Text Primary**: #F5F5F5
- **Text Secondary**: #A0A0A0

### Severity Colors

- **Extreme**: #EF4444 (Light) / #FF6B6B (Dark)
- **Medium**: #FFA500 (Light) / #FFB84D (Dark)
- **Low**: #22C55E (Light) / #4ADE80 (Dark)

---

## 10. Typography

### Font Families

- **Display/Headings**: Space Grotesk
- **Body**: Inter (web) / System (native)

### Scaled Typography Variants

| Variant       | Base Size | Line Height |
| ------------- | --------- | ----------- |
| displayLarge  | 38px      | 46px        |
| displayMedium | 32px      | 38px        |
| displaySmall  | 28px      | 34px        |
| h1            | 24px      | 31px        |
| h2            | 22px      | 29px        |
| h3            | 20px      | 26px        |
| h4            | 18px      | 23px        |
| bodyLarge     | 18px      | 27px        |
| bodyMedium    | 16px      | 24px        |
| bodySmall     | 14px      | 21px        |
| labelLarge    | 16px      | 22px        |
| labelMedium   | 14px      | 20px        |
| labelSmall    | 12px      | 17px        |
| caption       | 11px      | 15px        |

### Font Scaling

- Small: 85% of base sizes
- Medium: 100% of base sizes (default)
- Large: 125% of base sizes

---

## 11. Spacing System (8px Grid)

- xs: 4px
- sm: 8px
- md: 16px
- lg: 24px
- xl: 32px
- xxl: 48px

### Responsive Breakpoints

- **Mobile**: < 768px
- **Tablet**: 768px - 1024px
- **Desktop**: > 1024px

### Border Radius

- sm: 8px
- md: 12px
- lg: 16px
- xl: 24px
- xxl: 32px
- full: 9999px

---

## 12. Real-World Deployment Plan

To launch this web app publicly:

1. Finalize frontend implementation ✅
2. Connect backend AI prediction API
3. Deploy backend (e.g., cloud server)
4. Deploy frontend (e.g., Vercel / Netlify / cloud hosting)
5. Configure domain & SSL
6. Set up monitoring and analytics

---

## 13. Key Features Implemented

✅ OpenStreetMap integration with Leaflet
✅ Grid-based square cell overlays (Thailand-wide lat/lng bounding boxes)
✅ Mock AI prediction data (~510 cells, full Thailand)
✅ Light/Dark mode with Settings toggle
✅ Font size accessibility (S/M/L)
✅ Responsive design for all screen sizes
✅ Glassmorphism UI components
✅ Severity-based color coding
✅ Interactive map with zoom controls
✅ Temperature timeline display
✅ Warning banner for extreme heat alerts
✅ Thai/English language support

---

## 14. Future Integrations

### AI Backend Integration

The grid system is designed for easy AI integration:

```typescript
// Future: Replace mock data with API call
const realGridData = await fetch("/api/predictions");
// Map AI response to GridCell[] structure
// Call setGridData(realGridData) to update
```

### LINE OA Integration

- Push notifications for heatwave alerts
- Location-based safety recommendations

---

## 15. Troubleshooting

### Appearance.setColorScheme Error

If you see "Appearance.default.setColorScheme is not a function" on web:

- This is expected - the method only works on native platforms
- The app handles this gracefully with platform detection

### Font Size Scaling

The font size system uses global state via React Context:

- `useSettings` hook provides `fontSize`, `fontScale`, and `typography`
- `ScaledText` component automatically applies font scaling to all text
- All user-facing screens use `ScaledText` instead of plain `Text`
- Font scale: Small=0.85, Medium=1.0, Large=1.25

### Bottom Navigation

All primary screens include consistent floating bottom navigation:

- Map, Alerts, Safety (tab), Profile pages
- Safety Checklist modal page also includes navigation
- Dark mode support via `BottomNavStyle.dark`

---

_Last Updated: 2026-02-28_
_Project Version: 1.1_
