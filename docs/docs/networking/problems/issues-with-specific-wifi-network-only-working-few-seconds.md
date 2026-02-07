---
description: Troubleshooting guide for Wi-Fi connectivity issues caused by Docker subnet conflicts, where the network works for a few seconds and then breaks repeatedly.
---

# Specific (Wi-Fi) Network works for few seconds, breaks, then works again for few seconds

## Story
So I had really weird network problems on one specific Wi-Fi network on my laptop running Kubuntu.

The problem was that the network worked a few seconds after connecting, then stopped working for a few seconds and then
come back for a few seconds, over and over again. Sometimes it would not recover though.
Even using ping, the responses were interrupted, so a DNS or firewall problems seemed unlikely.
The connection status was still connected.
Because the network requires PEAP authentication, I thought that this would be the problem
(especially because it worked on all other devices I had).

But after trying all kinds of things, thinking it the network would block something or an authentication issue, the problem was rather simple.

Turns out, Docker, which was running on my laptop, was the problem because it was using the same network range (127.x.x.x).

## Solution
To verify that Docker was actually causing this issue, I have stopped it and deleted the network
(will be recreated automatically when starting Docker again):
```bash
sudo systemctl stop docker
sudo ip link delete docker0
```

Directly after executing these commands, the network instantly worked flawlessly.
To keep using Docker while on this network, we need to change the Docker subnet.

Create/Modify this file and add this option:
```json title="/etc/docker/daemon.json"
{
  "bip": "192.168.100.1/24"
}
```

Then restart Docker:
```bash
sudo systemctl restart docker
```