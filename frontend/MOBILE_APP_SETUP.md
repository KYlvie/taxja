# Mobile App Setup

This frontend now ships as a Capacitor app for Android and iOS.

## Core commands

```bash
npm run build:mobile
npm run mobile:sync
npm run mobile:android
npm run mobile:ios
npm run mobile:assets
npm run mobile:release:android
```

## Environment

- `VITE_API_BASE_URL`: explicit API base URL for web builds
- `VITE_MOBILE_API_BASE_URL`: API base URL used inside native apps when `VITE_API_BASE_URL` is not set
- `CAP_SERVER_URL`: optional live-reload URL for Capacitor during device testing

## What is already configured

- Web builds continue to use the existing Vite + PWA pipeline.
- Mobile builds use relative asset paths for the native WebView.
- The native shell sets up a non-overlay status bar and Android back-button handling.
- Native document flows support camera capture, device file picking, and save/share actions.
- Android app ID is `at.taxja.app`.
- iOS bundle identifier is `at.taxja.app`.
- Android and iOS marketing version are both `1.0.0`.
- Generated app icons and launch assets live in the native projects and PWA manifest.
- iOS camera and photo-library usage descriptions are configured in `ios/App/App/Info.plist`.

## Local toolchain

- A portable local Android toolchain can live in `.mobile-tools/`.
- Android release builds expect:
  - `.mobile-tools/jdk-21`
  - `.mobile-tools/android-sdk`
- `frontend/android/local.properties` points Gradle at that local SDK.

## Release outputs

- Android AAB: `frontend/android/app/build/outputs/bundle/release/app-release.aab`
- Android APK: `frontend/android/app/build/outputs/apk/release/app-release.apk`

## Signing

- Android release signing is read from `frontend/android/keystore.properties`.
- The actual keystore file is `frontend/android/app/taxja-upload.jks`.
- Both files are ignored by Git. Back them up before publishing updates, otherwise future app updates cannot be signed with the same key.

## Platform limits

- Android release packaging can be produced on this Windows machine.
- iOS native sync works on Windows, but App Store archives still require Xcode on macOS.

## Next reference

See `MOBILE_RELEASE_GUIDE.md` for the full store-readiness checklist.
