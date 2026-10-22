#!/usr/bin/env bash
set -euo pipefail
bash android/ci-gradle.sh connectedDebugAndroidTest
adb install -r android/distribuicao/DoceAtelie-Android-1.0.0.apk
adb shell am start -W -n br.com.doceatelie/.MainActivity
sleep 3
adb shell pidof br.com.doceatelie
adb shell screencap -p /sdcard/doce-apk.png
adb pull /sdcard/doce-apk.png android/distribuicao/teste-emulador.png
