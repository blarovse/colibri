# Monday Colibri Android Companion App

Android companion application for the Monday Multi-AI Personal Operating System.

## Features

- **Device Registration**: Securely register your Android device with the Monday laptop gateway
- **JWT Authentication**: Token-based authentication with encrypted storage
- **WebSocket Connection**: Real-time bidirectional communication with Monday
- **Voice Commands**: Send voice/text commands to Monday assistant
- **Action Approvals**: Review and approve/deny gated actions from your laptop
- **Status Dashboard**: Monitor connection status, active tasks, and notifications
- **Secure Storage**: Encrypted storage for tokens and sensitive data using AndroidX Security

## Architecture

```
app/
├── src/main/java/com/monday/colibri/
│   ├── ColibriApplication.kt       # Application class
│   ├── ui/                         # Compose UI screens
│   │   ├── MainActivity.kt         # Main activity & navigation
│   │   ├── Screens.kt              # Registration, Pairing, Dashboard
│   │   └── CommandAndApprovalScreens.kt
│   ├── network/                    # Network layer
│   │   ├── MondayApiService.kt     # Retrofit API interface
│   │   ├── MondayWebSocketClient.kt # WebSocket client
│   │   └── MondayWebSocketService.kt # Foreground service
│   ├── data/                       # Data models
│   │   └── Models.kt               # Request/Response data classes
│   └── security/                   # Security layer
│       └── SecureStorage.kt        # Encrypted SharedPreferences
└── src/main/res/                   # Android resources
```

## Build Instructions

### Prerequisites

1. **Android Studio** (Arctic Fox or newer)
2. **JDK 17**
3. **Android SDK** (API 34)
4. **Monday Gateway Server** running on your laptop

### Setup

1. **Open in Android Studio**:
   ```bash
   # Open Android Studio and select "Open an existing project"
   # Navigate to /workspace/colibri-app
   ```

2. **Sync Gradle**:
   - Android Studio will automatically sync Gradle files
   - Wait for dependencies to download

3. **Configure Server URL**:
   - Default: `http://10.0.2.2:8765` (Android emulator localhost)
   - For physical device: Use your laptop's IP address (e.g., `http://192.168.1.100:8765`)

### Build Commands

```bash
# Debug build
./gradlew assembleDebug

# Release build
./gradlew assembleRelease

# Install on connected device/emulator
./gradlew installDebug

# Run tests
./gradlew test
```

### Running the App

1. **Start Monday Gateway** on your laptop:
   ```bash
   cd /workspace/monday/android_gateway
   pip install -r requirements.txt
   python -m monday.android_gateway.server
   ```

2. **Run the Android app**:
   - Connect an Android device or start an emulator
   - Click "Run" in Android Studio or:
   ```bash
   ./gradlew installDebug
   ```

3. **Register Device**:
   - Enter device name and server URL
   - Tap "Register Device"
   - Note the 6-digit pairing code

4. **Complete Pairing**:
   - Open Monday dashboard on laptop
   - Enter the 6-digit code
   - App will automatically detect pairing confirmation

5. **Use the App**:
   - Send voice/text commands
   - Review pending approvals
   - Monitor task progress

## Configuration

### Server URL

- **Emulator**: `http://10.0.2.2:8765`
- **Physical device (same network)**: `http://<laptop-ip>:8765`
- **Production**: `https://your-domain.com`

### Permissions

The app requests these permissions:
- `INTERNET`: Network communication
- `POST_NOTIFICATIONS`: Show notifications (Android 13+)
- `FOREGROUND_SERVICE`: Maintain WebSocket connection
- `RECORD_AUDIO`: Voice input (optional)

## Security

- **Encrypted Storage**: Uses AndroidX Security library with AES256-GCM
- **JWT Tokens**: Secure token-based authentication
- **TLS**: Use HTTPS/WSS in production
- **No Raw Keys**: Only token references stored

## Dependencies

- **Jetpack Compose**: Modern UI toolkit
- **Retrofit**: REST API client
- **OkHttp**: HTTP & WebSocket client
- **AndroidX Security**: Encrypted storage
- **Material 3**: Material Design components
- **Navigation Compose**: In-app navigation

## Troubleshooting

### Connection Issues

1. **Check server is running**: `curl http://localhost:8765/health`
2. **Firewall**: Ensure port 8765 is open
3. **Network**: Device and laptop must be on same network
4. **Cleartext Traffic**: Enabled for development; use HTTPS in production

### Build Errors

```bash
# Clean and rebuild
./gradlew clean
./gradlew build

# Invalidate caches
File > Invalidate Caches / Restart
```

## Next Steps

1. **Voice Recognition**: Integrate speech-to-text for voice commands
2. **Push Notifications**: Firebase Cloud Messaging for offline notifications
3. **Biometric Auth**: Fingerprint/face unlock for app access
4. **Widgets**: Home screen widgets for quick actions
5. **Dark Mode**: Full dark/light theme support

## License

Part of the Monday Multi-AI Personal Operating System.
