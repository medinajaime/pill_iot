# Smart Pill Dispenser (智慧藥盒)

An IoT smart medication management system designed for Taiwan's elderly population. The companion app combines prescription recognition with automatic dispensing to help users manage their medications safely and effectively.

## Features

- **Prescription Scanning** - Scan Taiwan NHI prescription QR codes to automatically import medications
- **Medication Scheduling** - Daily and weekly medication schedule views
- **Adherence Tracking** - Track medication compliance with history and statistics
- **IoT Dispenser Integration** - Connect to smart pill dispenser via Bluetooth/WiFi
- **Caregiver Dashboard** - Allow family members to monitor medication adherence remotely
- **Multi-language Support** - English and Traditional Chinese (繁體中文)
- **Elderly-Friendly UI** - Large fonts, high contrast options, voice prompts

## Screenshots

*Coming soon*

## Getting Started

### Prerequisites

- Flutter SDK 3.16.0 or higher
- Android Studio / VS Code
- Java JDK 17
- Android SDK (API 23+)

### Installation

1. **Clone the repository**
   ```bash
   git clone git@github.com:medinajaime/pill_iot_dispenser.git
   cd pill_iot_dispenser
   ```

2. **Install dependencies**
   ```bash
   flutter pub get
   ```

3. **Generate code** (for freezed/json_serializable)
   ```bash
   dart run build_runner build --delete-conflicting-outputs
   ```

4. **Run the app**
   ```bash
   flutter run
   ```

### Firebase Setup (Required for Production)

1. Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
2. Enable Authentication, Firestore, Cloud Messaging, and Storage
3. Download `google-services.json` and place in `android/app/`
4. Run `flutterfire configure` to generate Firebase options
5. Uncomment Firebase initialization in `lib/main.dart`

## Project Structure

```
lib/
├── main.dart                 # App entry point
├── app.dart                  # MaterialApp configuration
├── core/
│   ├── localization/         # i18n (English & Chinese)
│   ├── router/               # GoRouter navigation
│   ├── theme/                # App theme & styling
│   └── utils/                # Utilities (QR parser, etc.)
├── data/
│   └── models/               # Data models (freezed)
├── presentation/
│   ├── providers/            # Riverpod state management
│   ├── screens/              # App screens
│   └── widgets/              # Reusable widgets
└── services/                 # Business logic & API services
```

## Tech Stack

| Category | Technology |
|----------|------------|
| Framework | Flutter 3.16+ |
| State Management | Riverpod |
| Navigation | GoRouter |
| Local Storage | Hive, SharedPreferences |
| Backend | Firebase (Auth, Firestore, Messaging, Storage) |
| Bluetooth | flutter_blue_plus |
| QR Scanning | mobile_scanner |
| Notifications | flutter_local_notifications |

## Building

### Debug APK
```bash
flutter build apk --debug
```

### Release APK
```bash
flutter build apk --release
```

### App Bundle (Play Store)
```bash
flutter build appbundle --release
```

Output location: `build/app/outputs/flutter-apk/`

## Configuration

### Environment Variables

Create `android/app/google-services.json` with your Firebase configuration (not committed to git).

### Changing App ID

Update the application ID in `android/app/build.gradle.kts`:
```kotlin
applicationId = "com.yourcompany.smartpilldispenser"
```

## Localization

The app supports:
- **English** (en-US)
- **Traditional Chinese** (zh-TW)

Language can be switched in Settings > Display Settings > Language.

To add translations, edit `lib/core/localization/app_localizations.dart`.

## Development

### Demo Mode

The app includes a demo mode with mock data for testing without a real dispenser. Toggle in Settings > Developer Options > Demo Mode.

### Running Tests
```bash
flutter test
```

### Code Generation
```bash
dart run build_runner watch  # Watch mode
dart run build_runner build --delete-conflicting-outputs  # One-time build
```

## Roadmap

See [TASKS.md](TASKS.md) for detailed integration tasks and remaining work.

### Priority Features
- [ ] Firebase backend integration
- [ ] Push notifications for medication reminders
- [ ] Real Bluetooth device pairing
- [ ] LINE messaging integration
- [ ] Voice prompts (Mandarin/Hokkien)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Authors

- **Marcus Canul**
- **Jaime Medina**

## License

This project is proprietary. All rights reserved.

## Acknowledgments

- Designed for Taiwan's National Health Insurance (NHI) prescription system
- Built with accessibility in mind for elderly users
- IoT hardware integration for automated pill dispensing
