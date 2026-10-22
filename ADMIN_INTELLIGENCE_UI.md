# Admin Intelligence Dashboard - UI Implementation

## Overview
A production-grade admin intelligence dashboard built with Next.js (TypeScript/React) and modern CSS styling.

## Location
- **Page**: `frontend/app/admin/intelligence/page.tsx`
- **Styles**: `frontend/app/admin/intelligence/page.css`

## Features Implemented

### 1. **Overview Tab** 🎯
- **5 Key Metrics Dashboard**:
  - High-Risk Organizations (⚠️) - Risk score > 70
  - Anomaly Flags (🚨) - Unacknowledged flags
  - Unread Smart Alerts (📢) - Actionable notifications
  - Churn Risk Organizations (📉) - May become inactive
  - Pending Documents (📋) - Awaiting review

- **Quick Actions Panel** - One-click buttons for:
  - Review high-risk organizations
  - Acknowledge anomaly flags
  - Act on smart alerts
  - Auto-approve low-risk documents

- **System Health Indicators** - Visual progress bars for:
  - Platform Health (85%)
  - Alert Response (72%)
  - Document Review (58%)

### 2. **Risk Scores Tab** 🎯
- **Data Table** with columns:
  - Organization ID
  - Type (NGO/Donor)
  - Risk Score (0-100, color-coded)
  - Confidence Level (LOW/MEDIUM/HIGH)
  - Factor breakdown:
    - Verification Status
    - Completion Rate
    - Donation Velocity
    - Account Age

- **Visual Indicators**:
  - Green badges: Good (< 40)
  - Yellow badges: Warning (40-70)
  - Red badges: Critical (> 70)

### 3. **Smart Alerts Tab** 🔔
- **Alert Cards Grid** with:
  - Alert type (INACTIVE_NGO, CHURN_RISK, etc.)
  - Priority level badge
  - Complete message
  - Recommended action
  - Timestamp
  - Color-coded by priority:
    - 🔴 URGENT - Red
    - 🟠 HIGH - Orange
    - 🟡 MEDIUM - Yellow
    - 🟢 LOW - Green

### 4. **Anomaly Flags Tab** ⚠️
- **Anomaly Cards** displaying:
  - Flag type (DUPLICATE_ACCOUNT, UNUSUAL_DONATION, etc.)
  - Severity level
  - Reasoning text
  - Acknowledgment status
  - Creation timestamp
  - Color-coded severity:
    - 🔴 CRITICAL - Red
    - 🟠 HIGH - Orange
    - 🟡 MEDIUM - Yellow
    - 🟢 LOW - Green

### 5. **Churn Risks Tab** 📉
- **Churn Risk Cards** showing:
  - Organization name
  - Churn risk score (0-100%)
  - Organization type (DONOR/NGO)
  - Intervention suggestions
  - Visual progress bar
  - Color-coded risk level

### 6. **Campaign Forecasts Tab** 🎯
- **Campaign Forecast Cards** displaying:
  - Project title
  - Success probability (0-100%)
  - Confidence level
  - Visual progress bar
  - Color-coded by likelihood:
    - Green: High success (> 70%)
    - Yellow: Medium success (40-70%)
    - Red: Low success (< 40%)

## Design Features

### **Visual Design**
- **Header**: Purple gradient (667eea → 764ba2)
- **Cards**: White backgrounds with colored left borders
- **Hover Effects**: Subtle lift animation on hover
- **Icons**: Emoji-based for visual clarity
- **Badges**: Color-coded severity/priority indicators

### **Layout**
- **Responsive Grid**: Auto-fit layouts
- **Tab Navigation**: Horizontal tabs with badge counters
- **Two-column on desktop**, single column on mobile
- **Max-width containers**: 1400px for readability

### **Color Scheme**
- 🔴 Red (#dc2626) - CRITICAL/URGENT
- 🟠 Orange (#f59e0b) - HIGH/WARNING  
- 🟡 Yellow (#f59e0b) - MEDIUM
- 🟢 Green (#10b981) - LOW/GOOD
- 🔵 Blue (#3b82f6) - INFO
- 🟣 Purple (#667eea) - Primary

### **Typography**
- **Headers**: Font size 1.5-2.5rem, weight 700-800
- **Body**: Font size 0.875-0.95rem, weight 400-600
- **Metric values**: Font size 2.5rem, weight 800
- **Labels**: Font size 0.75-0.875rem, uppercase, weight 600-700

### **Spacing**
- **Card padding**: 1.5-2rem
- **Gap between items**: 1-1.5rem
- **Section padding**: 2rem

## Interactive Elements

### **Quick Action Buttons**
- Colored backgrounds matching severity
- Icon + text layout
- Hover lift animation
- Full width on mobile

### **Data Tables**
- Fixed header with gradient background
- Hover row highlight
- Score badges with color coding
- Confidence level indicators
- Organization ID truncated with monospace font

### **Progress Bars**
- 8px height with rounded corners
- Gradient fills
- Smooth animations
- Percentage labels

## API Integration

The dashboard connects to these endpoints:
- `GET /api/admin/dashboard/summary` - Overall metrics
- `GET /api/admin/risk-scores` - Risk score data
- `GET /api/admin/smart-alerts` - Alert queue
- `GET /api/admin/anomalies` - Anomaly flags
- `GET /api/admin/churn-risks` - Churn predictions
- `GET /api/admin/campaign-forecasts` - Campaign forecasts

## Authentication

- Automatically redirects to `/admin/login` if not authenticated
- Checks auth via `GET /auth/me`
- Clears token on 401 error
- Handles 403 permission errors gracefully

## Loading States

- **Spinner animation** during data load
- **Error display** with icon and message
- **Empty states** with emoji and helpful text
- **Loading message**: "Loading intelligence data..."

## Responsive Design

### **Desktop (> 768px)**
- 5 metrics in grid
- 2+ column layouts
- Full-size tables

### **Mobile (< 768px)**
- Single column layouts
- Stacked action buttons
- Single column tables
- Font size adjustments
- Touch-friendly spacing

## Performance Optimizations

- Parallel data loading with Promise.all()
- Graceful degradation if some data fails
- Efficient CSS with flexbox/grid
- Minimal re-renders (useState)
- No external dependencies (emoji icons)

## Features

✅ Real-time dashboard summary
✅ 6 different intelligence views
✅ Color-coded severity/priority
✅ Responsive grid layouts
✅ Interactive hover effects
✅ Empty states and loading animations
✅ Error handling
✅ Mobile-friendly design
✅ Accessibility-friendly colors
✅ Emoji-based visual communication

## Future Enhancements

- [ ] Chart.js integration for visual analytics
- [ ] Real-time updates with WebSocket
- [ ] Filtering and sorting on tables
- [ ] Export to CSV/PDF
- [ ] Dark mode theme
- [ ] Advanced search functionality
- [ ] Custom date range filters
- [ ] Bulk action capabilities
- [ ] Notification preferences
- [ ] Admin dashboard analytics

## File Structure

```
frontend/app/admin/intelligence/
├── page.tsx          # Main component
└── page.css          # Styles
```

## Component Props

The page component is a client-side component that:
1. Checks authentication on mount
2. Loads dashboard data via API
3. Manages tab state
4. Renders 6 different views
5. Handles loading/error states

## Notes

- Uses Next.js `"use client"` directive for client-side rendering
- All API calls use the shared `api()` function from `@/lib/api`
- TypeScript interfaces for type safety
- CSS uses CSS Grid and Flexbox
- No external UI libraries (pure CSS)
- Gradient backgrounds for visual appeal
- Color gradients for depth perception
