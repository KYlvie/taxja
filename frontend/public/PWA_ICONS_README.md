# PWA Icons Generation Guide

This directory needs PWA icons for the Taxja application. Follow these steps to generate them:

## Required Icons

- `pwa-64x64.png` - Small icon for shortcuts
- `pwa-192x192.png` - Standard icon for home screen
- `pwa-512x512.png` - Large icon for splash screen
- `apple-touch-icon.png` - iOS home screen icon (180x180)
- `favicon.ico` - Browser favicon

## Icon Design Guidelines

### Brand Colors
- Primary: `#1976d2` (Blue)
- Secondary: `#764ba2` (Purple)
- Background: `#ffffff` (White)

### Design Elements
- Logo should be centered
- Use the "Taxja" wordmark or a stylized "T" symbol
- Include a subtle tax/finance icon (calculator, document, or euro symbol)
- Ensure good contrast for visibility on various backgrounds

## Generation Methods

### Option 1: Using Online Tools
1. Visit https://realfavicongenerator.net/
2. Upload your base logo (at least 512x512 PNG)
3. Configure settings:
   - iOS: Use solid background color
   - Android: Use maskable icon with safe zone
   - Windows: Use solid background
4. Download and extract to this directory

### Option 2: Using PWA Asset Generator
```bash
npm install -g pwa-asset-generator

# Generate all icons from a single source
pwa-asset-generator logo.svg ./public \
  --icon-only \
  --favicon \
  --maskable \
  --padding "10%"
```

### Option 3: Manual Creation
Use design tools like Figma, Sketch, or Photoshop:

1. Create a 512x512 canvas
2. Design the icon with 10% padding (safe zone for maskable icons)
3. Export at different sizes:
   - 512x512 (full quality)
   - 192x192 (standard)
   - 64x64 (small)
   - 180x180 (Apple touch icon)

## Maskable Icons

For Android adaptive icons, ensure:
- Important content stays within the central 80% circle
- Background extends to full canvas edges
- No transparency in maskable versions

## Testing

After generating icons:

1. Test on Android:
   - Add to home screen
   - Check icon appearance
   - Verify splash screen

2. Test on iOS:
   - Add to home screen
   - Check icon appearance
   - Verify standalone mode

3. Test on Desktop:
   - Install PWA
   - Check taskbar/dock icon
   - Verify window icon

## Placeholder Icons

Until proper icons are created, you can use placeholder icons:

```bash
# Create simple colored squares as placeholders
convert -size 512x512 xc:#1976d2 -gravity center \
  -pointsize 200 -fill white -annotate +0+0 "T" \
  pwa-512x512.png

convert pwa-512x512.png -resize 192x192 pwa-192x192.png
convert pwa-512x512.png -resize 64x64 pwa-64x64.png
convert pwa-512x512.png -resize 180x180 apple-touch-icon.png
```

## Resources

- [PWA Icon Guidelines](https://web.dev/add-manifest/)
- [Maskable Icons](https://web.dev/maskable-icon/)
- [iOS Icon Guidelines](https://developer.apple.com/design/human-interface-guidelines/app-icons)
