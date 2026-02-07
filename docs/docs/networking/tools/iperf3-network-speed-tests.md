---
description: Complete guide to using iperf3 for network speed testing, including installation on Linux, macOS, Windows, FreeBSD, and setting up a systemd service.
---

# iperf3: Network speed tests

iperf 3 is a useful tool that allows you to easily do (local) network speed tests between two computers.

## Usage
### Server
```bash
iperf3 -s
```
After executing this command, the server is started and no longer needs to be touched.
All the test related options are used from the client side.

### Client
To start a basic upload (client -> server) speed test, type this command: 
```
iperf3 -c x.x.x.x
```
Replace `x.x.x.x` with the IP address of the server.

#### Options
You can add options to the client command to e.g. reverse the speed test (upload/download) or
do a bidirectional speed test (upload and download at the same time).

Here is a short list of the probably most used options:

| Option    | Description                                                  |
|-----------|--------------------------------------------------------------|
| `-R`      | Run in reverse mode (server sends, client receives)          |
| `--bidir` | Run in bidirectional mode                                    |
| `-t 30`   | Time in seconds (e.g. 30s) to transmit for (default 10 secs) |

To get the full list of options + descriptions, type:
```bash
iperf3 --help
```


## Installation

### Debian/Ubuntu
```bash
sudo apt install iperf3
```

### Fedora / Red Hat / CentOS / Rocky
```bash
yum install iperf3
```

### Alpine Linux (often used for docker containers)
```bash
apk add iperf3
```

### FreeBSD
```bash
sudo pkg install benchmarks/iperf3
```

### macOS
```bash
brew install iperf3
```

### Windows
Download the latest version of iPerf3 from the official website: [iPerf3 Download](https://iperf.fr/iperf-download.php#windows)

### Android
Useful networking app that also integrates iPerf 3: [PingTools Network Utilities](https://play.google.com/store/apps/details?id=ua.com.streamsoft.pingtools&hl=de)

## Run as service
To always let the server run without opening a terminal,
you can create an iperf3 service that automatically gets started on boot.

Create this file:
```service title="/etc/systemd/system/iperf3.service"
[Unit]
Description=iperf3 server
After=syslog.target network.target auditd.service

[Service]
ExecStart=/usr/bin/iperf3 -s

[Install]
WantedBy=multi-user.target
```

Reload systemctl (this is needed after creating/modifying systemd service files):
```bash
systemctl daemon-reload
```

Start the iperf3 server:
```bash
systemctl start iperf3
```

Enable it so that it automatically start back up on reboot:
```
systemctl enable iperf3
```

Inspired by: [https://askubuntu.com/questions/1251443/start-iperf3-deamon-at-startup](https://askubuntu.com/a/1251448){:target="_blank"}