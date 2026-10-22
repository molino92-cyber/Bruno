#!/usr/bin/env bash
set -euo pipefail
bash android/ci-gradle.sh connectedDebugAndroidTest
adb install -r android/distribuicao/DoceAtelie-Android-1.0.0.apk
adb shell am start -W -n br.com.doceatelie/.MainActivity
sleep 2
previous_app_uid=$(adb shell pm list packages -U br.com.doceatelie | awk '$1=="package:br.com.doceatelie" {print $2}')
adb shell am force-stop br.com.doceatelie
adb install -r android/distribuicao/DoceAtelie-Android-1.0.1.apk
updated_app_uid=$(adb shell pm list packages -U br.com.doceatelie | awk '$1=="package:br.com.doceatelie" {print $2}')
test -n "$previous_app_uid"
test "$previous_app_uid" = "$updated_app_uid"
adb shell am start -W -n br.com.doceatelie/.MainActivity
sleep 3
adb shell pidof br.com.doceatelie
adb shell screencap -p /sdcard/doce-apk.png
adb pull /sdcard/doce-apk.png android/distribuicao/teste-emulador.png
