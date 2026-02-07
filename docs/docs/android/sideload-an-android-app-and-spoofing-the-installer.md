---
description: How to sideload Android apps and spoof the installer source using ADB to make apps appear as installed from Google Play Store, useful for Android Auto.
---

# Sideload an Android App and spoofing the installer

When installing an Android app, the system keeps track of where it came from.
For example, if you install an app from the Google Play Store, the app info will show something like "Installed from Google Play Store".
Normally, it doesn't matter where the app came from, but in some cases like Android Auto, it does.

Android Auto does not show apps that were installed from sources other than Google Play.
This prevents you from using modded apps in AA (e.g. Spotify,...).

You can enable developer mode in AA, but in my case, the apps from different sources do not always show up and I have to reconnect AA in hopes it will be there on the next try.
With spoofing the installed app, it is way more consistent (however it's still missing sometimes) and you don't need to enable the developer mode.

To do this, you just need to use the `-i` argument and define the package name of the installer app:
```bash
adb install -i "com.android.vending" -r .\path\to\your.apk
```
