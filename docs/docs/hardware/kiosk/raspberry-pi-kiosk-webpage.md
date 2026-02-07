---
description: Step-by-step guide to set up a Raspberry Pi as a web kiosk with auto-start, Chromium or Firefox in kiosk mode, and overlay filesystem for reliability.
---

# Set up Raspberry Pi as web kiosk

## Compatibility
These instrutions haven't been fully tested from start to end because they were created after I set up the two kiosks I currently have.
It should work with any recent Raspberry Pi OS (e.g. 12) though.
Let me know if there's a issue somewhere in these instructions.

## Preparations
- Install the headless RPi OS (if you need to use the desktop variant for some reason, configure it to boot to console)
- Make sure auto-login is enabled:
    - `sudo raspi-config` -> 1 System Options -> S6 Auto Login -> Yes
- Make sure `openbox` is installed
- Make sure `unclutter` is installed (optional, can be commented out in the script below)
    

## Display & Browser setup
1. Create/modify the file `/home/pi/.xinitrc`and add:
``` title="/home/pi/.xinitrc"
#!/bin/bash
openbox-session &
exec /home/pi/kiosk.sh
```

2. Set the correct permissions: `chmod +x /home/pi/.xinitrc`

3. Create/modify the file `/home/pi/.bash_profile` and add:
```title="/home/pi/.bash_profile"
[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx -- -nocursor
```

4. Set the correct permissions: `chmod +x /home/pi/.bash_profile`

5. Create the file `/home/pi/kiosk.sh` and add:
```bash title="/home/pi/kiosk.sh" linenums="1"
#!/bin/bash

URL="http://homeassistant.local"
CHROMIUM_PREFERENCES_FILE="/home/$USER/.config/chromium/Default/Preferences"

# Remove mouse cursor (optional)
unclutter -idle 5 -root &

# Disable screensavers (if they are enabled by default)
xset -dpms
xset s off
xset s noblank

# Prevent Chromium addons from automatically updating (which may open a new tab which is then displayed instead of our kiosk page)
sed -i 's|"update_url":"https://clients2.google.com/service/update2/crx"|"update_url":"https://localhost"|' "$CHROMIUM_PREFERENCES_FILE"

# Remove warning popups in Chrome
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' /home/$USER/.config/chromium/Default/Preferences
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' /home/$USER/.config/chromium/Default/Preferences

####################################################################################
## Choose your browser by uncommenting either "chromium-browser" or "firefox-esr" ##
####################################################################################

# Launch chromium browser
#chromium-browser --noerrdialogs --disable-infobars --kiosk "$URL"

# Some more chrome flags that can be used:
# --hide-scrollbars

# Launch Firefox
#firefox-esr --kiosk "$URL"
```

6. Set the correct permissions: `chmod +x /home/pi/kiosk.sh`
7. Reboot. The kiosk should automatically start on the next boot.

## Custom browser scripts
You can use the browser extension [Tampermonkey](https://www.tampermonkey.net/) for writing custom browser scripts.
With such a script, you can e.g. automatically fill in form fields and click buttons, very useful if you need to log in somewhere.

In some cases, such a script will not work after rebooting because the browser window may not be focused properly. In that case it can help to (virtually) press a key.

1. Create a new script, e.g. `/home/pi/press-key.sh`
```
#!/bin/bash
xdotool key F2
```

2. Set the correct permissions: `chmod +x /home/pi/press-key.sh`

3. Install a cronjob (`crontab -e`)
```crontab
# Execute key-press script to focus browser to allow custom scripts
* * * * * DISPLAY=:0 /home/pi/press-key.sh
```

## Setup daily reboots
To make sure there are no permanent hangs (e.g. a website that no longer refreshes on its own) and to keep the system more reliable, you should set up daily rebooting.
You can do this by setting up a cronjob (`crontab -e`) with: `0 3 * * * sudo reboot`


## Finalize setup
If everything is set up and works correctly, you can enable the overlay file system on the raspberry pi.

- `sudo raspi-config` -> 4 Performance Options -> P2 Overlay File System -> Yes -> Ok -> No -> Ok -> Reboot

You can keep the boot partition writeable as normally there isn't written much anyway.

The overlay file system will not only greatly reduce SD card wear but also prevents corruption, full storage issues or similar.
This will give you a setup that should require little to no maintenance.
For making updates or other changes, don't forget to disable the overlay file system before doing them, otherwise everything will be reverted on the next reboot.

### What the overlay file system actually does
If the overlay file system is enabled, your Raspberry Pi’s root filesystem is mounted as read-only, and a temporary writable layer (in RAM) is placed on top. You can still "write" files (create, edit, or delete them) just like normal, but all changes are stored in the temporary layer. After a reboot, everything is reset to the previous state because the modifications in the temporary layer are discarded and the underlying system remains unchanged. With a standard read-only filesystem, modifying files would not be possible at all.

## WiFi troubleshooting
If you experience conenctivity issues, here are some troubleshooting steps you can try.

### Find out what's causing issues
Example commands that can help you identify the problem:

- `iw wlan1 link` - Check the signal strength (60-70 should be okay, -80 dBm or lower is really bad)
- `sudo journalctl -u wpa_supplicant --since "8 hours ago"`
- `sudo journalctl -u NetworkManager --since "8 hours ago"`
- `sudo journalctl -b --since "8 hours ago" | grep wlan`

### Set infinity reconnect attempts (untested if that really works)
Create and edit the file `/etc/NetworkManager/conf.d/99-retry.conf`:
```conf
[connection]
autoconnect-retries=0  # 0 means infinite
```

### For hidden networks (currently not sure if it really improves anything, we'll see)
Make sure that your network service knows that it's hidden.

#### If using nmcli
Type `nmcli connection show <network-name>` and look for the line `802-11-wireless.hidden`. If it's set to `yes` and your network is hidden, it's already set up correctly.
If it's set to `no`, you should set it to `yes` with `sudo nmcli connection modify <network-name> 802-11-wireless.hidden yes`

#### If using wpa_supplicant directly
Add this line in your network config, e.g. add it below `psk=xxx`: `scan_ssid=1`

#### How to find out what you're using
If `/etc/wpa_supplicant/wpa_supplicant.conf` contains your network config, you're using `wpa_supplicant` directly.
If `/etc/wpa_supplicant/wpa_supplicant.conf` does not contain your network config or does not exist at all, you're likely not using `wpa_supplicant`.
Check if the command `nmcli connection show` shows your connected wifi network. If it shows it, you're using `nmcli`.