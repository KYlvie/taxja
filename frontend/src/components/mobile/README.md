# Mobile Components

This directory contains mobile-specific components optimized for touch interfaces and small screens.

## Components

### CameraCapture

Native camera integration for document scanning.

**Features:**
- Real-time camera preview
- Front/back camera switching
- Document frame overlay
- Capture tips and guidance
- Error handling with retry
- Landscape/portrait support

**Usage:**
```tsx
import { CameraCapture } from '@/components/mobile/CameraCapture';

<CameraCapture
  onCapture={(file) => uploadDocument(file)}
  onClose={() => setShowCamera(false)}
/>
```

## Hooks

### useTouchGestures

Touch gesture detection and handling.

**Features:**
- Swipe detection (left/right/up/down)
- Pinch-to-zoom support
- Configurable threshold
- Fast swipe detection

**Usage:**
```tsx
import { useTouchGestures } from '@/hooks/useTouchGestures';

const gestures = useTouchGestures({
  onSwipeLeft: () => navigate('/next'),
  onSwipeRight: () => navigate('/prev'),
  threshold: 50
});

<div {...gestures}>Swipeable content</div>
```

### useIsMobile

Device type detection.

**Usage:**
```tsx
import { useIsMobile } from '@/hooks/useTouchGestures';

const isMobile = useIsMobile();

{isMobile ? <MobileView /> : <DesktopView />}
```

### useIsTouchDevice

Touch capability detection.

**Usage:**
```tsx
import { useIsTouchDevice } from '@/hooks/useTouchGestures';

const isTouch = useIsTouchDevice();

{isTouch && <TouchOptimizedButton />}
```

### usePullToRefresh

Pull-to-refresh functionality.

**Usage:**
```tsx
import { usePullToRefresh } from '@/hooks/useTouchGestures';

const pullToRefresh = usePullToRefresh(async () => {
  await refreshData();
});

<div {...pullToRefresh}>
  {pullToRefresh.isPulling && <RefreshIndicator />}
  <Content />
</div>
```

## Design Guidelines

### Touch Targets

- Minimum size: 44x44px
- Adequate spacing: 8px minimum
- Visual feedback on touch
- No hover-only interactions

### Typography

- Minimum font size: 14px
- Line height: 1.5 for readability
- Adequate contrast (WCAG AA)

### Layout

- Mobile-first approach
- Flexible layouts (Grid/Flexbox)
- Safe area support (iOS notch)
- Landscape mode considerations

### Performance

- Lazy load images
- Compress uploads
- Minimize animations
- Optimize bundle size

## Browser Support

- **iOS Safari**: 12+
- **Chrome Mobile**: 80+
- **Firefox Mobile**: 80+
- **Samsung Internet**: 12+

## Testing

### Device Testing

Test on real devices:
- iPhone (various models)
- Android phones (various manufacturers)
- Tablets (iPad, Android tablets)

### Emulator Testing

Use Chrome DevTools:
1. Open DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Select device preset
4. Test touch interactions

### Performance Testing

1. Lighthouse audit (mobile)
2. Network throttling (3G)
3. CPU throttling (4x slowdown)
4. Memory profiling

## Accessibility

- Touch targets meet WCAG guidelines
- Screen reader support
- Keyboard navigation (when available)
- High contrast mode support
- Reduced motion support

## Future Enhancements

- Haptic feedback
- Gesture customization
- Offline mode indicators
- Progressive image loading
- Voice input support
