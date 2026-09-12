#!/bin/bash
cd android
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew assembleDebug
