# Instalar Atlas en iPhone o iPad

La app es universal, requiere iOS/iPadOS 17 o posterior y se conecta al servidor Atlas del Mac por la red local. El índice, R y las credenciales de IA permanecen en el Mac.

## Compilar e instalar con Xcode

1. Instala Xcode desde Apple y abre `ios/AtlasRAG.xcodeproj`.
2. En el target **AtlasRAG → Signing & Capabilities**, selecciona tu propio equipo de Apple y un identificador de aplicación disponible. Activa la firma automática.
3. Conecta tu dispositivo y selecciónalo como destino. Pulsa **Run**. Activa Developer Mode y autoriza tu firma si el sistema lo solicita.
4. En Atlas del Mac abre **Servidor → iPhone / iPad · Red local…** y activa HTTPS.
5. Conecta ambos a la misma red. Copia el enlace de conexión del Mac en la app móvil o abre el QR con Cámara. Inicia sesión con tu usuario de Atlas.

Tu cuenta de Apple y el perfil determinan la duración de la firma. Renueva la instalación desde Xcode cuando sea necesario. Este repositorio no contiene certificados privados, cuentas, perfiles de aprovisionamiento ni identificadores de dispositivos del desarrollador.

## Paquete de dispositivo sin firmar

[`releases/AtlasRAG-iOS-unsigned.ipa`](releases/AtlasRAG-iOS-unsigned.ipa) contiene la compilación arm64 para dispositivo y no incluye perfiles personales. **No puede instalarse directamente sin firmarlo con tu equipo de Apple.** El procedimiento recomendado es compilar desde el proyecto Xcode, que gestiona la firma y el dispositivo.

Para reproducir las compilaciones sin firma, desde la raíz del repositorio:

```sh
zsh scripts/build_ios.sh
```

Se generan `dist/AtlasRAG-Simulator.app` y `dist/AtlasRAG-iOS-unsigned.app`. Para una instalación de desarrollo con tu cuenta ya configurada en Xcode:

```sh
zsh scripts/install_ipad.sh TU_DEVICE_UDID TU_DEVELOPMENT_TEAM
```

No compartas tu perfil, certificado privado ni credenciales de Apple.

## Conexión y permisos

La app declara únicamente el permiso de red local. No solicita fotos, contactos, micrófono, cámara ni localización. La Cámara del sistema puede abrir el QR de emparejamiento. El cliente comprueba la huella SHA-256 del certificado del Mac; no acepta certificados arbitrarios ni instala certificados raíz. El QR contiene dirección privada y huella pública, sin contraseña.

Los usuarios y permisos se validan en el servidor en cada operación. El navegador de carpetas recorre carpetas del Mac. La gestión de modelos y servidores solo está disponible para administradores. OAuth de OpenAI se autoriza en el Mac; el envío de contexto requiere consentimiento en la operación.
