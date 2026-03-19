# Mobile Release Guide

This project is now prepared for a production-style mobile release flow.

## Ready now

- Capacitor shells exist for Android and iOS.
- Mobile navigation and safe-area layout are implemented.
- Native file picker, camera upload, and save/share flows are implemented.
- Release icons and splash screens are generated from `resources/logo.svg` and `resources/logo-dark.svg`.
- Android release signing is configured through a local keystore.
- Android release artifacts can be built locally on Windows.

## Commands

```bash
npm run mobile:assets
npm run mobile:sync
npm run mobile:release:android
```

## Generated Android artifacts

- App Bundle: `android/app/build/outputs/bundle/release/app-release.aab`
- APK: `android/app/build/outputs/apk/release/app-release.apk`

## Android signing details

- Application ID: `at.taxja.app`
- Version name: `1.0.0`
- Version code: `1`
- Upload key alias: `taxja-upload`
- Upload certificate SHA-256: `E6:AEB8:78:C0:DA:BE:E1:8F:20:E3:3D:61:8B:72:D5:B4:C9:E4:2B:7C:AC:09:47:5D:CE:FF:70:35:D9:DF:9E`

Important:

- Keep `android/app/taxja-upload.jks` and `android/keystore.properties` in a safe backup.
- Losing that key means you cannot ship updates for the same Android app listing.

## Google Play checklist

1. Create the app in Google Play Console with package name `at.taxja.app`.
2. Upload `app-release.aab`.
3. Fill in store listing copy, screenshots, feature graphic, privacy policy URL, and support contact.
4. Complete Data safety and content rating questionnaires.
5. Verify Play App Signing enrollment and store the upload key backup safely.

## iOS checklist

1. Move the `frontend/ios` project to a Mac with Xcode installed.
2. Open `ios/App/App.xcworkspace`.
3. Set the Apple Developer team and signing profile.
4. Confirm bundle identifier `at.taxja.app`.
5. Archive the app and upload it through Xcode Organizer.
6. Complete App Store Connect metadata, privacy labels, screenshots, and review notes.

## Current blocker for final iOS submission

The codebase is ready to sync to iOS, but the final archive and App Store upload cannot be completed on Windows. That last step must be done on macOS with Xcode and an Apple Developer account.
