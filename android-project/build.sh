#!/usr/bin/env bash
# Build Violet Music Editor APK without Gradle.
# Uses arm64 Debian aapt2/zipalign and Java-based d8/apksigner.
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")" && pwd)"
SDK="/opt/android-sdk"
DEBIAN_BT="/usr/lib/android-sdk/build-tools/debian"
PLATFORM="$SDK/platforms/android-34/android.jar"
BUILD="$PROJECT/build"

AAPT2="$DEBIAN_BT/aapt2"
ZIPALIGN="$DEBIAN_BT/zipalign"
APKSIGNER="$DEBIAN_BT/apksigner"
D8="$SDK/build-tools/34.0.0/d8"

rm -rf "$BUILD"
mkdir -p "$BUILD/res" "$BUILD/gen" "$BUILD/classes" "$BUILD/dex"

echo "==> aapt2 compile"
"$AAPT2" compile --dir "$PROJECT/res" -o "$BUILD/res/res.zip"

echo "==> aapt2 link"
"$AAPT2" link \
  -o "$BUILD/base.apk" \
  -I "$PLATFORM" \
  --manifest "$PROJECT/AndroidManifest.xml" \
  -R "$BUILD/res/res.zip" \
  --java "$BUILD/gen" \
  --auto-add-overlay

echo "==> javac"
javac -source 8 -target 8 -Xlint:-options \
  -classpath "$PLATFORM" \
  -d "$BUILD/classes" \
  $(find "$BUILD/gen" -name '*.java') \
  $(find "$PROJECT/java" -name '*.java')

echo "==> d8"
"$D8" --min-api 21 --lib "$PLATFORM" --output "$BUILD/dex" \
  $(find "$BUILD/classes" -name '*.class')

echo "==> add classes.dex to APK"
( cd "$BUILD/dex" && zip -q -j "$BUILD/base.apk" classes.dex )

echo "==> zipalign"
"$ZIPALIGN" -f 4 "$BUILD/base.apk" "$BUILD/aligned.apk"

echo "==> generate debug keystore"
keytool -genkeypair -v -keystore "$BUILD/debug.keystore" \
  -storepass android -alias androiddebugkey -keypass android \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -dname "CN=Android Debug,O=Android,C=US" 2>&1 | tail -1

echo "==> apksigner"
"$APKSIGNER" sign \
  --ks "$BUILD/debug.keystore" --ks-pass pass:android --key-pass pass:android \
  --out "$PROJECT/VioletMusicEditor.apk" "$BUILD/aligned.apk"

echo "==> verify"
"$APKSIGNER" verify --print-certs "$PROJECT/VioletMusicEditor.apk" 2>&1 | head -3
echo "==> DONE"
ls -la "$PROJECT/VioletMusicEditor.apk"
