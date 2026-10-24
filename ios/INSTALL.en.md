# Install Atlas on iPhone or iPad

[Español](INSTALL.md) · [iOS project](README.en.md) · [Project README](../README.en.md)

This universal app requires iOS/iPadOS 17 or later and connects to the Mac's Atlas server over the local network. The index, R and AI credentials remain on the Mac.

## Build and install with Xcode

1. Install Xcode from Apple and open `ios/AtlasRAG.xcodeproj`.
2. Under **AtlasRAG → Signing & Capabilities**, select your own Apple team and an available application identifier. Enable automatic signing.
3. Connect your device and select it as the run destination. Choose **Run**. Enable Developer Mode and trust your development signature if the system requests it.
4. In Atlas on the Mac, open **Server → iPhone / iPad · Local network…** and enable HTTPS.
5. Connect both devices to the same network. Copy the Mac connection link into the mobile app, or scan its QR code with the system Camera. Sign in with your Atlas account.

Your Apple account and provisioning profile determine signature validity. Renew the installation through Xcode when necessary. The repository contains no private certificates, accounts, provisioning profiles or developer device identifiers.

## Unsigned device package

[`releases/AtlasRAG-iOS-unsigned.ipa`](releases/AtlasRAG-iOS-unsigned.ipa) contains the arm64 device build without personal provisioning profiles. **It cannot be installed directly without signing it with your own Apple team.** Building the Xcode project is recommended because Xcode manages signing and device installation.

To reproduce unsigned builds, run from the repository root:

```sh
zsh scripts/build_ios.sh
```

This produces `dist/AtlasRAG-Simulator.app` and `dist/AtlasRAG-iOS-unsigned.app`. To perform a development installation after configuring your own account in Xcode:

```sh
zsh scripts/install_ipad.sh YOUR_DEVICE_UDID YOUR_DEVELOPMENT_TEAM
```

Do not share your provisioning profile, private certificate or Apple credentials.

## Connection and permissions

The app declares only local-network permission. It does not request photos, contacts, microphone, camera or location access. The system Camera can open the pairing QR code. The client checks the SHA-256 fingerprint of the Mac certificate; it neither accepts arbitrary certificates nor installs root certificates. The QR code contains a private address and a public fingerprint, without a password.

The server validates users and permissions for every operation. The folder browser navigates directories on the Mac. Only administrators can manage models and engines. OpenAI OAuth is authorized on the Mac; sending context requires consent for the operation.

If the Mac address changes, obtain a new connection link from its local-network menu. Verify certificate changes on the Mac before pairing again. Do not disable certificate verification to work around connection errors.
