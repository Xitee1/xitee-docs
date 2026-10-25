---
description: Network boot a Raspberry Pi 3B, 3B+, 4 or 5 without an SD card. The root filesystem lives on an iSCSI disk of a Proxmox VM, so it gets snapshots and Proxmox Backup Server backups like any other VM. Uses OPNsense Dnsmasq for DHCP and a small Debian VM for TFTP, iSCSI and NFS.
---

# Raspberry Pi: Network boot with the root filesystem on iSCSI

!!! info "AI-generated guide"
    This guide was written by an AI. I did not write the text myself. It has not been tested end to end yet, so expect rough edges and let me know if something does not work as described.

The Pi boots over the network and uses a virtual disk of a Proxmox VM as its root filesystem. From the Pi's point of view it is a normal block device (`/dev/sda` with ext4), from Proxmox's point of view it is just another VM disk. That gives you:

- No SD card wear and no corrupted cards after power loss
- Snapshots and Proxmox Backup Server (PBS) backups of the Pi like of any VM
- Restoring a Pi = restoring a VM

## How it works
| Step | What happens | Served by |
|---|---|---|
| 1. DHCP | Pi gets its IP and the address of the TFTP server (option 66) | OPNsense (Dnsmasq) |
| 2. TFTP | Firmware loads `config.txt`, kernel and initramfs from a folder named after the Pi's **serial number** | Netboot VM |
| 3. iSCSI | initramfs logs into the iSCSI target and mounts it as `/` | Netboot VM |
| 4. NFS | The TFTP folder is mounted as `/boot/firmware`, so kernel updates land where the Pi boots from | Netboot VM |

??? info "Why not NFS for the root filesystem?"
    NFS root is simpler to set up, but it is a file share, not a disk. Some software (Docker overlay storage, SQLite, file locking) behaves differently on NFS. iSCSI is a block device, the Pi formats it with ext4 itself and everything behaves like a local disk. A whole-disk restore via PBS also matches the "Pi = VM" idea better.

## Compatibility
| | Pi 3B | Pi 3B+ | Pi 4 | Pi 5 |
|---|---|---|---|---|
| Network boot lives in | Boot ROM (buggy) | Boot ROM (fixed) | EEPROM bootloader | EEPROM bootloader |
| Enable network boot | OTP bit, **permanent** | enabled from factory | boot order in EEPROM, changeable any time | same as Pi 4 |
| SD card in operation | **tiny SD with only `bootcode.bin`** (ROM bugs) | none | none | none |
| First TFTP request | `bootcode.bin` (TFTP root) | `bootcode.bin` (TFTP root) | `start4.elf` in the serial-number folder | files in the serial-number folder |
| Kernel / initramfs (64-bit Pi OS) | `kernel8.img` / `initramfs8` | `kernel8.img` / `initramfs8` | `kernel8.img` / `initramfs8` | `kernel_2712.img` / `initramfs_2712` |
| Ethernet | 100 Mbit/s | ~300 Mbit/s (behind USB 2.0) | 1 Gbit/s | 1 Gbit/s |
| PoE HAT | no | yes | yes | yes |

Tested target OS: Raspberry Pi OS Lite 64-bit. Netboot VM: Debian 13.

??? info "Why is the OTP bit on the Pi 3B permanent?"
    OTP means *one-time programmable*: tiny fuses inside the SoC. A bit can be burned from 0 to 1 once, there is no circuit to reset it.

    The Pi 3 has no writable bootloader storage. Network boot is part of the boot ROM inside the chip, and the only persistent place the ROM can read a setting from before any OS runs is the OTP memory.

    Raspberry Pi did not enable the new boot modes by default because they first wanted to check that they work as expected. Later, bugs showed up in the ROM, which were fixed in the 3B+. The 3B+ ships with the bit already set.

    Setting it is harmless in practice: the SD card is still tried first. USB and network are only tried if no bootable SD card is present.

    The Pi 4 and 5 have their own EEPROM bootloader, so the boot order is a normal setting there.

## Before you start
- A DHCP server that can send **option 66** (TFTP server) to the Pi. This guide uses OPNsense with **Dnsmasq**. If you are still on ISC DHCP, I recommend migrating since ISC is end-of-life: [OPNsense: Migrate from ISC DHCP to Dnsmasq](../../networking/opnsense/migrate-isc-dhcp-to-dnsmasq.md). ISC DHCP, Kea or any other DHCP server that can set option 66 works as well, only the menu paths differ.
- The Netboot VM and the Pis must be in the **same subnet**. The Pi 3 boot ROM cannot reach a TFTP server through a router.
- One SD card with Raspberry Pi OS Lite 64-bit for the initial setup of each Pi.

Values in angle brackets like `<HOST>` are placeholders. Every step that uses one has a box *Values used in this step* that tells you where to get it.

## Part 1: One-time setup
### 1.1 Create the Netboot VM
In the Proxmox GUI, on the node whose storage should hold the Pi disks:

| Setting | Value |
|---|---|
| OS | Debian 13 netinst, only *SSH server* + *standard system utilities* |
| CPU / RAM | 1 vCPU, 1 GB |
| SCSI controller | VirtIO SCSI single |
| Disk `scsi0` | 8 GB (system) |
| Network | same bridge/VLAN as the Pis |
| Options | *Start at boot* on, *Start/Shutdown order* `1` |

The disks for the Pis are added later, one per Pi.

!!! tip "Start order"
    The Pis cannot boot without this VM. Give it a low start order so it is up early after a node reboot.

### 1.2 Fixed IP for the VM (OPNsense)
Services → Dnsmasq DNS & DHCP → tab *Hosts*: add a fixed assignment for the VM (MAC from Proxmox → VM → Hardware → Network Device). Apply and restart the VM's network or reboot it.

From here on, this address is **`<VM-IP>`**. Example: `192.168.1.20`.

### 1.3 Packages (VM)
```bash
apt install targetcli-fb dnsmasq nfs-kernel-server
```

Make the iSCSI configuration survive reboots:
```bash
systemctl enable --now rtslib-fb-targetctl.service
```

### 1.4 TFTP server (VM)
Check the interface name with `ip a` (usually `ens18`).

```ini title="/etc/dnsmasq.d/tftp.conf"
# TFTP only, no DNS and no DHCP
port=0
interface=ens18
bind-interfaces
enable-tftp
tftp-root=/srv/tftp
```

Create the TFTP root **before** restarting, otherwise dnsmasq refuses to start (`TFTP directory /srv/tftp inaccessible`):
```bash
mkdir -p /srv/tftp
systemctl restart dnsmasq
systemctl status dnsmasq --no-pager
```

### 1.5 TFTP server option (OPNsense)
Services → Dnsmasq DNS & DHCP

1. Tab *DHCP tags* → `+` → *Name*: `rpi` → Save.

    !!! note "Create the tag first"
        The *Tag* fields in the other dialogs are dropdowns that only list existing tags. Typing a new name there only searches and shows *No results matched*.

2. Tab *DHCP options* → `+` (bottom right of the table):

| Field | Value |
|---|---|
| Interface | `Any` |
| Type | `Set` |
| Option | `tftp-server [66]` |
| Option6 | `None` |
| Tag | `rpi` (select from the dropdown) |
| Value | `<VM-IP>` |
| Force | off |

Apply. Only hosts with the `rpi` tag receive the TFTP server, other PXE clients in the network are not affected.

!!! warning "IP address, not a hostname"
    The Pi boot ROM has no DNS resolver. Option 66 must contain the IP address.

!!! tip "Different DHCP server"
    With ISC DHCP, Kea or another DHCP server, the goal is the same: the Pi's fixed assignment gets option 66 with the IP of the Netboot VM. Ideally only the Pis get it.

??? info "Why no ProxyDHCP?"
    Many guides run a second dnsmasq as *ProxyDHCP* next to the router. That exists for consumer routers that cannot send custom DHCP options. OPNsense can, so one DHCP server is enough. If a Pi hangs in DHCP or boot-loops, *DHCP reply delay* in Dnsmasq → General or a ProxyDHCP on the VM are possible workarounds.

## Part 2: Per Pi
Repeat this part for every Pi.

!!! info "The SD card is only a workbench"
    You set up the Pi on an SD card first. Later, the **whole system** on that card is copied 1:1 to the iSCSI disk (root filesystem) and to the TFTP folder (kernel, initramfs, boot config). Everything installed and configured on the SD card, including the iSCSI client, ends up in the network-booted system. After the switch the card is no longer used.

    Start with a **fresh installation**. An old card with random software and settings on it would be copied as well.

### 2.1 Install the Pi from SD card (Pi)
1. Raspberry Pi Imager: *Raspberry Pi OS Lite (64-bit)*, set hostname, user and SSH.

    The hostname is **`<HOST>`** from here on. Use lowercase letters, digits and hyphens only. Example: `kitchen-pi`.

2. Boot the Pi from the SD card and update:
```bash
sudo apt update && sudo apt full-upgrade -y && sudo reboot
```

### 2.2 Fixed IP and tag for the Pi (OPNsense)
Get the MAC address of the Pi (line `link/ether`, e.g. `b8:27:eb:12:34:56`):
```bash
ip link show eth0
```

Services → Dnsmasq DNS & DHCP → tab *Hosts*: add a fixed assignment with this MAC and select `rpi` in *Tag [set]*. Apply.

This address is **`<PI-IP>`** from here on. Example: `192.168.1.50`.

### 2.3 Enable network boot (Pi)
=== "Pi 3B"
    Check the OTP bit:
    ```bash
    vcgencmd otp_dump | grep 17:
    ```

    | Output | Meaning |
    |---|---|
    | `17:3020000a` | already enabled |
    | `17:1020000a` | not enabled yet |

    Enable it (**permanent**, see [Compatibility](#compatibility)):
    ```bash
    echo "program_usb_boot_mode=1" | sudo tee -a /boot/firmware/config.txt
    sudo reboot
    ```

    Check again, it must show `17:3020000a`. Then remove the line from `/boot/firmware/config.txt` so the card does not program other Pis by accident.

=== "Pi 3B+"
    ```bash
    vcgencmd otp_dump | grep 17:
    ```

    Must show `17:3020000a` (factory default). If not, proceed as for the Pi 3B.

=== "Pi 4 / Pi 5"
    ```bash
    sudo raspi-config
    ```

    1. *Advanced Options → Bootloader Version → Latest*
    2. *Advanced Options → Boot Order → Network Boot*
    3. Exit and reboot.

    Check:
    ```bash
    sudo rpi-eeprom-config
    ```
    `BOOT_ORDER` must contain a `2`, e.g. `0xf21` = SD card, then network, then retry.

### 2.4 Add a disk for the Pi (Proxmox)
Netboot VM → Hardware → Add → Hard Disk:

| Setting | Value |
|---|---|
| Bus/Device | SCSI, next free number (first Pi `scsi1`, second Pi `scsi2`, ...) |
| Storage | SSD storage, ideally LVM-thin or ZFS so snapshots and thin provisioning work |
| Size | 32 GB, see below |
| Discard, SSD emulation | on |

On the VM, find the stable path of the new disk:
```bash
ls -l /dev/disk/by-id/ | grep scsi
```

This path is **`<DISK>`** from here on. Example: `/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1`.

??? info "Does the disk have to match the SD card size?"
    No. The system is copied file by file, not as a disk image. The VM disk only has to hold the data actually in use plus room to grow, the size of the SD card does not matter. A fresh Raspberry Pi OS Lite uses about 2 to 3 GB, check with `df -h /` on the Pi.

    The disk can be enlarged later while the Pi is running:

    1. Proxmox → Netboot VM → Hardware → disk → Disk Action → Resize
    2. On the Pi, let iSCSI pick up the new size and grow the filesystem:
    ```bash
    sudo iscsiadm -m session --rescan
    sudo resize2fs /dev/sda
    ```

    No partition needs to be resized because the disk has no partition table.

### 2.5 iSCSI target (VM)
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<HOST>` | hostname of the Pi: run `hostname` on the Pi | `kitchen-pi` |
    | `<DISK>` | path of the Pi's VM disk: run `ls -l /dev/disk/by-id/ \| grep scsi` on the VM | `/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1` |
    | `<IQN-PREFIX>` | `iqn.` + year-month + `.` + a domain you own, reversed. Same for every Pi | `iqn.2026-10.com.example` |

iSCSI identifies the target (VM side) and the initiator (Pi side) by an *IQN*. Both are built from the values above:

| Name | How to build it | Example |
|---|---|---|
| Target IQN | `<IQN-PREFIX>:netboot.<HOST>` | `iqn.2026-10.com.example:netboot.kitchen-pi` |
| Initiator IQN | `<IQN-PREFIX>:<HOST>` | `iqn.2026-10.com.example:kitchen-pi` |

??? info "What is an IQN?"
    ```
    iqn.2026-10.com.example:netboot.kitchen-pi
    │   │       │           └─ free text
    │   │       └─ a domain you own, reversed
    │   └─ year and month you owned that domain
    └─ fixed prefix
    ```

    The date and domain only exist to make names globally unique. Neither the Pi nor the server checks them, they only compare the full string. Pick any domain you own and any date, and never change it afterwards.

Open `targetcli`:
```bash
targetcli
```

Run inside `targetcli`:

=== "Template"
    ```text title="targetcli"
    /backstores/block create name=<HOST> dev=<DISK>
    /iscsi create <IQN-PREFIX>:netboot.<HOST>
    /iscsi/<IQN-PREFIX>:netboot.<HOST>/tpg1/luns create /backstores/block/<HOST>
    /iscsi/<IQN-PREFIX>:netboot.<HOST>/tpg1/acls create <IQN-PREFIX>:<HOST>
    saveconfig
    exit
    ```

=== "Example"
    ```text title="targetcli"
    /backstores/block create name=kitchen-pi dev=/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1
    /iscsi create iqn.2026-10.com.example:netboot.kitchen-pi
    /iscsi/iqn.2026-10.com.example:netboot.kitchen-pi/tpg1/luns create /backstores/block/kitchen-pi
    /iscsi/iqn.2026-10.com.example:netboot.kitchen-pi/tpg1/acls create iqn.2026-10.com.example:kitchen-pi
    saveconfig
    exit
    ```

| Command | What it does |
|---|---|
| `backstores/block create` | registers the VM disk with the iSCSI service under an internal name |
| `iscsi create` | creates the target the Pi connects to |
| `luns create` | attaches the disk to the target |
| `acls create` | only an initiator with exactly this IQN may connect |
| `saveconfig` | saves everything |

??? tip "Undo a step"
    Every `create` has a matching `delete`, e.g. `/backstores/block delete <HOST>`. Registering a backstore does not write anything to the disk itself. `targetcli` saves on exit by default, so a later `delete` is needed even after leaving the shell.

### 2.6 TFTP folder and NFS export (VM)
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<HOST>` | hostname of the Pi: run `hostname` on the Pi | `kitchen-pi` |
    | `<SERIAL>` | serial number of the Pi: run `grep Serial /proc/cpuinfo` on the Pi, take the **last 8 characters**, lowercase | `00000000a1b2c3d4` → `a1b2c3d4` |
    | `<PI-IP>` | fixed IP of the Pi: OPNsense → Dnsmasq → *Hosts*, or `hostname -I` on the Pi | `192.168.1.50` |

The Pi firmware requests its boot files from a TFTP folder named after its **serial number**. The real folder is named after the hostname, the serial number only becomes a symlink to it. Replacing a Pi later then means moving one symlink.

??? info "Why the serial number?"
    The boot firmware knows nothing about iSCSI or your configuration, it only knows its own serial number. Only the files loaded from that folder contain the iSCSI settings.

=== "Template"
    ```bash
    mkdir -p /srv/tftp/<HOST>
    ln -s <HOST> /srv/tftp/<SERIAL>
    ls -l /srv/tftp/
    ```

=== "Example"
    ```bash
    mkdir -p /srv/tftp/kitchen-pi
    ln -s kitchen-pi /srv/tftp/a1b2c3d4
    ls -l /srv/tftp/
    ```

`ls` must show the folder and the symlink pointing to it:

```text title="Example output"
total 4
lrwxrwxrwx 1 root root   10 Oct 25 16:39 a1b2c3d4 -> kitchen-pi
drwxr-xr-x 2 root root 4096 Oct 25 16:41 kitchen-pi
```

| Entry | Meaning |
|---|---|
| `kitchen-pi` (`d` at the start) | real folder, the boot files go here later |
| `a1b2c3d4 -> kitchen-pi` (`l` at the start) | symlink named after the serial number, pointing to the folder. The number before the date is just the length of the target name |

Export the **hostname folder** (never the symlink) to the Pi:

=== "Template"
    ```text title="/etc/exports"
    /srv/tftp/<HOST>  <PI-IP>(rw,sync,no_subtree_check,no_root_squash)
    ```

=== "Example"
    ```text title="/etc/exports"
    /srv/tftp/kitchen-pi  192.168.1.50(rw,sync,no_subtree_check,no_root_squash)
    ```

```bash
exportfs -ra
```

### 2.7 iSCSI client (Pi)
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<IQN-PREFIX>` | `iqn.` + year-month + `.` + a domain you own, reversed. Same for every Pi | `iqn.2026-10.com.example` |
    | `<HOST>` | hostname of the Pi: run `hostname` on the Pi | `kitchen-pi` |
    | `<VM-IP>` | IP of the Netboot VM: OPNsense → Dnsmasq → *Hosts*, or `ip a` on the VM | `192.168.1.20` |

```bash
sudo apt install open-iscsi nfs-common
```

`nfs-common` is needed to mount the TFTP folder as `/boot/firmware` via NFS.

The IQNs must be exactly the ones used for the iSCSI target on the VM:

===! "Template"
    ```ini title="/etc/iscsi/initiatorname.iscsi"
    InitiatorName=<IQN-PREFIX>:<HOST>
    ```

=== "Example"
    ```ini title="/etc/iscsi/initiatorname.iscsi"
    InitiatorName=iqn.2026-10.com.example:kitchen-pi
    ```

===! "Template"
    ```ini title="/etc/iscsi/iscsi.initramfs"
    ISCSI_INITIATOR=<IQN-PREFIX>:<HOST>
    ISCSI_TARGET_NAME=<IQN-PREFIX>:netboot.<HOST>
    ISCSI_TARGET_IP=<VM-IP>
    ISCSI_TARGET_PORT=3260
    ```

=== "Example"
    ```ini title="/etc/iscsi/iscsi.initramfs"
    ISCSI_INITIATOR=iqn.2026-10.com.example:kitchen-pi
    ISCSI_TARGET_NAME=iqn.2026-10.com.example:netboot.kitchen-pi
    ISCSI_TARGET_IP=192.168.1.20
    ISCSI_TARGET_PORT=3260
    ```

Change the existing lines in `/etc/iscsi/iscsid.conf`:
```ini title="/etc/iscsi/iscsid.conf"
node.session.timeo.replacement_timeout = -1  # queue I/O until the VM is back, never fail
node.conn[0].timeo.noop_out_interval = 0     # no keepalive pings, avoids recovery on short hiccups
node.conn[0].timeo.noop_out_timeout = 0      # same
```

The root session is created in the initramfs, so also set the timeout at boot:
```text title="/etc/tmpfiles.d/iscsi-timeout.conf"
w /sys/class/iscsi_session/session*/recovery_tmo - - - - -1
```

??? info "Why wait forever?"
    The default `replacement_timeout` is 120 seconds. A negative value means: keep I/O queued until the session is logged in again, without any limit.

    | | Timeout expires (default) | `-1` |
    |---|---|---|
    | Pending writes | fail, data is lost | written as soon as the VM is back |
    | Filesystem | ext4 switches to read-only | stays writable |
    | Programs | crash or hang with errors | continue |
    | VM back again | Pi stays broken, power-cycle needed | Pi recovers by itself |

    While the VM is unreachable, programs that need the disk freeze, everything in RAM keeps running. The amount of unwritten data is limited by the kernel (`vm.dirty_ratio`): once the limit is reached, writing programs are paused, nothing is dropped. Data still in RAM is only lost if the Pi loses power during the outage.

    There is no real downside: while the VM is gone, the Pi hangs either way. The only difference is that without a timeout it can recover by itself once the VM is back. With a timeout it stays broken and always needs a power-cycle.

Rebuild the initramfs and check:
```bash
sudo update-initramfs -u
grep auto_initramfs /boot/firmware/config.txt
ls /boot/firmware/initramfs*
```
`auto_initramfs=1` must be set (add it otherwise) and a fresh `initramfs8` (Pi 3/4) or `initramfs_2712` (Pi 5) must exist.

### 2.8 Connect and format the iSCSI disk (Pi)
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<VM-IP>` | IP of the Netboot VM: OPNsense → Dnsmasq → *Hosts*, or `ip a` on the VM | `192.168.1.20` |
    | `<IQN-PREFIX>` | `iqn.` + year-month + `.` + a domain you own, reversed. Same for every Pi | `iqn.2026-10.com.example` |
    | `<HOST>` | hostname of the Pi: run `hostname` on the Pi | `kitchen-pi` |

===! "Template"
    ```bash
    sudo systemctl restart iscsid
    sudo iscsiadm -m discovery -t st -p <VM-IP>
    sudo iscsiadm -m node -T <IQN-PREFIX>:netboot.<HOST> -p <VM-IP> --login
    lsblk
    ```

=== "Example"
    ```bash
    sudo systemctl restart iscsid
    sudo iscsiadm -m discovery -t st -p 192.168.1.20
    sudo iscsiadm -m node -T iqn.2026-10.com.example:netboot.kitchen-pi -p 192.168.1.20 --login
    lsblk
    ```

The new 32 GB disk is `/dev/sda`, the SD card is `mmcblk0`. Format the whole disk without a partition table:
```bash
sudo mkfs.ext4 -L piroot /dev/sda
sudo blkid /dev/sda
```

The value of `UUID="..."` is **`<UUID>`** from here on.

```text title="Example output"
/dev/sda: LABEL="piroot" UUID="3f6c2b1e-8a4d-4c7e-9b21-5d0e7a9c4f12" BLOCK_SIZE="4096" TYPE="ext4"
```

### 2.9 Copy the system (Pi)
```bash
sudo mount /dev/sda /mnt
sudo rsync -aAXHx --info=progress2 / /mnt/
```
`-x` stays on the root filesystem. `/boot/firmware`, `/proc`, `/sys`, `/dev` and `/run` are created as empty folders only.

### 2.10 fstab on the iSCSI disk (Pi)
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<UUID>` | UUID of the iSCSI disk: run `sudo blkid /dev/sda` on the Pi, value of `UUID="..."` | `3f6c2b1e-8a4d-4c7e-9b21-5d0e7a9c4f12` |
    | `<VM-IP>` | IP of the Netboot VM: OPNsense → Dnsmasq → *Hosts*, or `ip a` on the VM | `192.168.1.20` |
    | `<HOST>` | hostname of the Pi: run `hostname` on the Pi | `kitchen-pi` |

Replace the whole file:
===! "Template"
    ```text title="/mnt/etc/fstab"
    proc  /proc  proc  defaults  0 0
    UUID=<UUID>  /  ext4  defaults,noatime,_netdev  0 1
    <VM-IP>:/srv/tftp/<HOST>  /boot/firmware  nfs  defaults,_netdev  0 0
    ```

=== "Example"
    ```text title="/mnt/etc/fstab"
    proc  /proc  proc  defaults  0 0
    UUID=3f6c2b1e-8a4d-4c7e-9b21-5d0e7a9c4f12  /  ext4  defaults,noatime,_netdev  0 1
    192.168.1.20:/srv/tftp/kitchen-pi  /boot/firmware  nfs  defaults,_netdev  0 0
    ```

### 2.11 Boot files to the TFTP folder (Pi)
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<VM-IP>` | IP of the Netboot VM: OPNsense → Dnsmasq → *Hosts*, or `ip a` on the VM | `192.168.1.20` |
    | `<HOST>` | hostname of the Pi: run `hostname` on the Pi | `kitchen-pi` |
    | `<UUID>` | UUID of the iSCSI disk: run `sudo blkid /dev/sda` on the Pi, value of `UUID="..."` | `3f6c2b1e-8a4d-4c7e-9b21-5d0e7a9c4f12` |

===! "Template"
    ```bash
    sudo mkdir -p /mnt2
    sudo mount -t nfs <VM-IP>:/srv/tftp/<HOST> /mnt2
    sudo rsync -rlt /boot/firmware/ /mnt2/
    ```

=== "Example"
    ```bash
    sudo mkdir -p /mnt2
    sudo mount -t nfs 192.168.1.20:/srv/tftp/kitchen-pi /mnt2
    sudo rsync -rlt /boot/firmware/ /mnt2/
    ```

In `cmdline.txt`, change only the root device and add `ip=dhcp`. Everything else stays as it is (WiFi region, cloud-init settings from the Raspberry Pi Imager, etc.):

| Before | After |
|---|---|
| `root=PARTUUID=...` (SD card) | `ip=dhcp root=UUID=<UUID>` (iSCSI disk, network up in the initramfs) |

===! "Template"
    ```bash
    sudo sed -i 's|root=PARTUUID=[^ ]*|ip=dhcp root=UUID=<UUID>|' /mnt2/cmdline.txt
    cat /mnt2/cmdline.txt
    ```

=== "Example"
    ```bash
    sudo sed -i 's|root=PARTUUID=[^ ]*|ip=dhcp root=UUID=3f6c2b1e-8a4d-4c7e-9b21-5d0e7a9c4f12|' /mnt2/cmdline.txt
    cat /mnt2/cmdline.txt
    ```

The file must still be **one single line**:

```text title="Example result"
console=serial0,115200 console=tty1 ip=dhcp root=UUID=3f6c2b1e-8a4d-4c7e-9b21-5d0e7a9c4f12 rootfstype=ext4 fsck.repair=yes rootwait cfg80211.ieee80211_regdom=DE ds=nocloud;i=rpi-imager-1234567890
```

??? info "What is `ds=nocloud;i=...`?"
    Since Raspberry Pi OS Trixie, the Raspberry Pi Imager applies its settings (user, SSH, WiFi, ...) via cloud-init on the first boot. This parameter tells cloud-init where its data is and which instance it belongs to. Keep it unchanged: cloud-init then knows the setup already ran and does not apply it again.

### 2.12 bootcode.bin in the TFTP root (VM, Pi 3B / 3B+ only, once)
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<HOST>` | hostname of the Pi: run `hostname` on the Pi | `kitchen-pi` |

The Pi 3 needs `bootcode.bin` before anything else. Who reads it from where:

| Model | Reads `bootcode.bin` from | Copy in the TFTP root needed? |
|---|---|---|
| Pi 3B+ | TFTP root (`/srv/tftp/bootcode.bin`) | **yes** |
| Pi 3B with tiny SD card | the tiny SD card (step 2.13) | no, but it is the easiest source for creating that card |
| Pi 4 / 5 | not used | no |

Copy it from the Pi's boot files into the TFTP root:

===! "Template"
    ```bash
    cp /srv/tftp/<HOST>/bootcode.bin /srv/tftp/
    ```

=== "Example"
    ```bash
    cp /srv/tftp/kitchen-pi/bootcode.bin /srv/tftp/
    ```

If `cp` reports *No such file or directory*, your Raspberry Pi OS image does not ship the file. Get it from the official Raspberry Pi firmware repository instead:
```bash
wget -O /srv/tftp/bootcode.bin https://github.com/raspberrypi/firmware/raw/master/boot/bootcode.bin
```

`bootcode.bin` is **not specific to a Pi**: it contains no serial number, hostname or configuration and is identical for every Pi 3. One copy in the TFTP root serves all Pi 3 on this VM, so this step is only needed once. Keep it there, it is only about 50 KB.

### 2.13 Switch over (Pi)
Unmount everything and shut down the Pi:
```bash
sudo umount /mnt2 /mnt
sudo iscsiadm -m node -u
sudo poweroff
```

Keep the SD card with the full system as a fallback.

=== "Pi 3B"
    The Pi 3B needs a **tiny SD card** that contains nothing but `bootcode.bin`. Its boot ROM has network boot bugs, the newer `bootcode.bin` from the card works around them. The card is only read at boot, never written, so wear is not an issue. Any size works. Since `bootcode.bin` is the same for every Pi 3, the card is not tied to this Pi either: it works in any Pi 3B, and you can prepare several identical cards in advance.

    Do this on a Linux PC.

    !!! note "Values used in this step"
        | Placeholder | Where to get it | Example |
        |---|---|---|
        | `<VM-IP>` | IP of the Netboot VM: OPNsense → Dnsmasq → *Hosts*, or `ip a` on the VM | `192.168.1.20` |
        | `<SD-DEVICE>` | the SD card: insert it and run `lsblk`, it is the new disk with the matching size | `/dev/sdc` |

    1. Get `bootcode.bin` from the VM:

        ===! "Template"
            ```bash
            scp root@<VM-IP>:/srv/tftp/bootcode.bin .
            ```

        === "Example"
            ```bash
            scp root@192.168.1.20:/srv/tftp/bootcode.bin .
            ```

    2. Prepare the card: one FAT32 partition, nothing else.

        **GUI:** KDE Partition Manager or GNOME Disks → select the SD card → new partition table *MS-DOS (MBR)* → one partition over the whole card, filesystem *FAT32* → apply. Then copy `bootcode.bin` to the card in the file manager.

        **CLI:**

        !!! danger "Check `<SD-DEVICE>` twice"
            These commands erase the whole device. A wrong device name wipes another disk.

        ===! "Template"
            ```bash
            lsblk
            sudo umount <SD-DEVICE>*
            sudo wipefs -a <SD-DEVICE>
            sudo parted -s <SD-DEVICE> mklabel msdos mkpart primary fat32 1MiB 100%
            sudo mkfs.vfat -F 32 <SD-DEVICE>1
            sudo mount <SD-DEVICE>1 /mnt
            sudo cp bootcode.bin /mnt/
            ls /mnt
            sudo umount /mnt
            ```

        === "Example"
            ```bash
            lsblk
            sudo umount /dev/sdc*
            sudo wipefs -a /dev/sdc
            sudo parted -s /dev/sdc mklabel msdos mkpart primary fat32 1MiB 100%
            sudo mkfs.vfat -F 32 /dev/sdc1
            sudo mount /dev/sdc1 /mnt
            sudo cp bootcode.bin /mnt/
            ls /mnt
            sudo umount /mnt
            ```

        `ls /mnt` must show only `bootcode.bin`.

    3. Insert the tiny SD card into the Pi. It stays there permanently.

=== "Pi 3B+ / 4 / 5"
    Remove the SD card. Nothing else is needed.

Power on the Pi.

## Verify
| Where | Command | Expected |
|---|---|---|
| VM | `journalctl -u dnsmasq -f` while the Pi boots | Pi 3: `sent .../bootcode.bin`, then files from the serial-number folder. Pi 4/5: files from the serial-number folder directly |
| Pi 4/5 | HDMI screen during boot | diagnostics screen shows IP, TFTP server and serial number |
| Pi | `sudo iscsiadm -m session` | one session to the target |
| Pi | `findmnt /` and `findmnt /boot/firmware` | `/dev/sda` and NFS |
| Pi | `cat /sys/class/iscsi_session/session1/recovery_tmo` | `-1` |

Enable TRIM so deleted space is returned to the thin-provisioned VM disk:
```bash
sudo systemctl enable --now fstrim.timer
```

## Troubleshooting
| Symptom | Cause / fix |
|---|---|
| No TFTP requests in the dnsmasq log | Pi host lacks the `rpi` tag, option 66 missing, or Pi and VM in different subnets |
| `file .../<SERIAL>/... not found` | symlink missing or wrong. Check `ls -l /srv/tftp/`, serial in lowercase? |
| Pi 3B boots unreliably without the tiny SD card | expected, boot ROM bug. Use the SD card with `bootcode.bin` |
| Pi hangs in DHCP or boot-loops | boot ROM timing bug. Try *DHCP reply delay* in Dnsmasq → General |
| Pi 4/5 does not try network boot | `BOOT_ORDER` without `2`, or outdated bootloader (step 2.3) |
| `Waiting for root device` | initramfs without iSCSI (step 2.7 done before 2.9?), or ACL IQN does not match the Pi IQN |
| Pi loses the connection shortly after boot | NetworkManager reconfigures `eth0`. Mark `eth0` as unmanaged in NetworkManager |
| Boot fails after a kernel update | `/boot/firmware` was not mounted via NFS during the update |

## Operation
| Situation | What to do |
|---|---|
| Short reboot of the Proxmox node | nothing, the Pi freezes and continues afterwards |
| Longer maintenance | shut down the Pis first |
| Pi hangs after an outage | power-cycle it. Pi 3B+/4/5 with a PoE HAT via the switch port, Pi 3B via a smart plug |
| Backup | the PBS backup of the Netboot VM contains all Pi disks (crash-consistent) |
| Restore | restoring the Netboot VM restores all Pis. For a single Pi: restore to a new VMID and reassign only its disk |
| Performance | the Pi 3B with 100 Mbit/s is not suited for databases or heavy I/O |

## Recovery
The system does not live on the Pi, so almost everything can be repaired from the Netboot VM without touching the Pi hardware.

| Problem | Where to fix it |
|---|---|
| Pi does not boot after a change to `cmdline.txt` or `config.txt` | [Fix the boot files](#fix-the-boot-files) |
| Broken `fstab`, network config or other system file | [Fix files on the root disk](#fix-files-on-the-root-disk) |
| Broken package or system update, commands needed | [Run commands in the Pi system](#run-commands-in-the-pi-system) |
| Everything broken | [Roll back](#roll-back) |
| You want to see what happens during boot | [See the boot process](#see-the-boot-process) |

### Fix the boot files
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<HOST>` | hostname of the Pi, also the folder name in `/srv/tftp/` on the VM: `ls -l /srv/tftp/` | `kitchen-pi` |

The boot files are plain files on the VM. Edit them directly, then power-cycle the Pi.

===! "Template"
    ```bash
    nano /srv/tftp/<HOST>/cmdline.txt
    nano /srv/tftp/<HOST>/config.txt
    ```

=== "Example"
    ```bash
    nano /srv/tftp/kitchen-pi/cmdline.txt
    nano /srv/tftp/kitchen-pi/config.txt
    ```

### Fix files on the root disk
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<DISK>` | path of the Pi's VM disk: run `ls -l /dev/disk/by-id/ \| grep scsi` on the VM | `/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1` |

!!! danger "Only while the Pi is off"
    Never mount the disk on the VM while the Pi is using it. Two systems writing to the same ext4 filesystem destroy it.

1. Shut down the Pi, or cut its power if it hangs.
2. On the VM, check that no iSCSI session is active anymore:
```bash
targetcli sessions
```
It must report `(no open sessions)`. After cutting the power this can take up to about a minute.

3. Release the disk from the iSCSI service. As long as the target is active, it holds the disk exclusively and `mount` fails with *Can't open blockdev*:
```bash
targetcli saveconfig
targetctl clear
```

    !!! warning "Affects all Pis"
        This stops the iSCSI target for **every** Pi on this VM. Running Pis freeze and continue once the target is restored in step 5.

4. Mount the disk, fix the file, unmount. Use the `by-id` path, `/dev/disk/by-uuid/...` does not exist on the VM because the Pi formatted the disk over iSCSI and the VM never noticed:

===! "Template"
    ```bash
    mount <DISK> /mnt
    nano /mnt/etc/fstab
    umount /mnt
    ```

=== "Example"
    ```bash
    mount /dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1 /mnt
    nano /mnt/etc/fstab
    umount /mnt
    ```

5. Restore the iSCSI target and check that it is back:
```bash
targetctl restore
targetcli ls
```
`targetcli ls` must show the backstore, the target with its ACL and the LUN again. Without this step no Pi can boot.

6. Power on the Pi.

### Run commands in the Pi system
!!! note "Values used in this step"
    | Placeholder | Where to get it | Example |
    |---|---|---|
    | `<DISK>` | path of the Pi's VM disk: run `ls -l /dev/disk/by-id/ \| grep scsi` on the VM | `/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1` |
    | `<HOST>` | hostname of the Pi, also the folder name in `/srv/tftp/` on the VM | `kitchen-pi` |

When files alone are not enough (e.g. a broken package), you can run the Pi's own programs on the VM. The VM is x86, the Pi system is ARM, so `qemu-user-static` emulates the ARM binaries. Slow, but `apt`, `dpkg` and `update-initramfs` work.

Same rules as above: **the Pi must be off** (`targetcli sessions` shows `(no open sessions)`).

Release the disk from the iSCSI service (affects all Pis on this VM):
```bash
targetcli saveconfig
targetctl clear
```

Once, on the VM:
```bash
apt install qemu-user-static
```

Mount the disk, the boot files and the system folders, then switch into the Pi system:

===! "Template"
    ```bash
    mount <DISK> /mnt
    mount --bind /srv/tftp/<HOST> /mnt/boot/firmware
    for d in proc sys dev dev/pts; do mount --bind /$d /mnt/$d; done
    chroot /mnt /bin/bash
    ```

=== "Example"
    ```bash
    mount /dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi1 /mnt
    mount --bind /srv/tftp/kitchen-pi /mnt/boot/firmware
    for d in proc sys dev dev/pts; do mount --bind /$d /mnt/$d; done
    chroot /mnt /bin/bash
    ```

Check that you are inside the Pi system, it must show `aarch64`:
```bash
uname -m
```

Repair, e.g. `dpkg --configure -a` or `apt install --reinstall <package>`. Then leave, unmount everything and restore the iSCSI target:
```bash
exit
umount -R /mnt
targetctl restore
targetcli ls
```

### Roll back
| Method | When |
|---|---|
| Proxmox snapshot of the Netboot VM | quick undo after a risky change. Take the snapshot **before** the change |
| PBS restore | older state. Restoring the whole VM affects all Pis. For a single Pi: restore to a new VMID and move only its disk to the Netboot VM |

Shut down the affected Pis before rolling back. The boot files in `/srv/tftp/` are on the VM's system disk and are rolled back with the VM, not with the Pi disk.

### See the boot process
| Method | Extra hardware | What you see |
|---|---|---|
| `journalctl -u dnsmasq -f` on the VM | no | whether the Pi requests its boot files and which ones |
| Serial console | USB-UART adapter on the Pi's GPIO pins, connected to another computer nearby | the complete boot including initramfs, also when the network fails. `console=serial0,115200` is already in `cmdline.txt` |
| Network KVM (e.g. PiKVM, NanoKVM, JetKVM) on HDMI | yes, permanently attached | screen and keyboard in the browser |

??? note "Kernel log over the network (netconsole, untested)"
    The kernel can send its messages via UDP to another host. On the Pi, `netconsole` is a kernel module, so it has to be in the initramfs and configured with the module syntax.

    On the Pi:
    ```bash
    echo netconsole | sudo tee -a /etc/initramfs-tools/modules
    sudo update-initramfs -u
    ```

    Append to `cmdline.txt` (same single line), with the IP of the VM (`<VM-IP>`, e.g. `192.168.1.20`):

    ===! "Template"
        ```text
        netconsole.netconsole=@/eth0,6666@<VM-IP>/
        ```

    === "Example"
        ```text
        netconsole.netconsole=@/eth0,6666@192.168.1.20/
        ```

    Listen on the VM:
    ```bash
    apt install netcat-openbsd
    nc -klu 6666
    ```

    Messages start once the network driver is up, so very early boot errors are not covered. Not tested with this setup yet.

## Replace a Pi
A new Pi has a new serial number and a new MAC address. The iSCSI disk, target and IQN stay the same, so the new Pi boots exactly the old system.

| Item | Changes? |
|---|---|
| iSCSI disk, target, IQN | no |
| `/etc/exports`, `fstab` | no (they point to the hostname folder) |
| symlink `<SERIAL>` | **yes** |
| MAC in OPNsense | **yes** |

1. Shut down and disconnect the old Pi.
2. Prepare the new Pi:

| Model | Preparation |
|---|---|
| Pi 3B | boot once from a normal SD card, set the OTP bit (step 2.3), note the serial. Then insert the tiny SD card with `bootcode.bin` |
| Pi 3B+ | boot once from a normal SD card and note the serial |
| Pi 4 / 5 | boot once from a normal SD card, enable network boot (step 2.3), note the serial |

3. Move the symlink on the VM. Old and new serial: run `grep Serial /proc/cpuinfo` on each Pi (booted from SD), last 8 characters, lowercase. `<HOST>` stays the same.
===! "Template"
    ```bash
    rm /srv/tftp/<OLD-SERIAL>
    ln -s <HOST> /srv/tftp/<NEW-SERIAL>
    ```

=== "Example"
    ```bash
    rm /srv/tftp/a1b2c3d4
    ln -s kitchen-pi /srv/tftp/e5f6a7b8
    ```
4. OPNsense → Dnsmasq → *Hosts* → entry of the Pi → new MAC → Apply. IP and tag stay.
5. Power on the new Pi.

!!! tip "Changing the model"
    64-bit Raspberry Pi OS ships the firmware and kernels for all models, so the same disk usually boots on a Pi 3, 4 or 5. Run `sudo update-initramfs -u -k all` on the old Pi first, so the iSCSI initramfs exists for every kernel. A Pi 3 additionally needs `bootcode.bin` in the TFTP root (step 2.12).

??? info "Alternative for Pi 4 / 5 only"
    The EEPROM setting `TFTP_PREFIX` can make the firmware use a fixed string or the MAC address instead of the serial number as folder name. The symlink works the same way for every model, so this guide sticks with it.

## Sources
- [Raspberry Pi blog: Pi 3 booting part I (OTP, boot modes)](https://www.raspberrypi.com/news/pi-3-booting-part-i-usb-mass-storage-boot/){:target="_blank"}
- [Raspberry Pi docs (fork): Network boot on the Pi 3](https://github.com/naushir/documentation/blob/master/hardware/raspberrypi/bootmodes/net.md){:target="_blank"}
- [nobodd: Netboot on the Pi](https://nobodd.readthedocs.io/en/latest/explain-pi-netboot.html){:target="_blank"}
- [openSUSE: netboot-rpi3b (DHCP options)](https://github.com/openSUSE/netboot-rpi3b){:target="_blank"}
- [Warmest Robot: Raspberry Pi Network Boot Guide 2.0](https://warmestrobot.com/blog/2024/06/27/raspberry-pi-network-boot-guide-2/){:target="_blank"}
- [zenn.dev: Raspberry Pi 4B PXE + iSCSI network boot](https://zenn.dev/korosuke613/articles/raspberry-pi-pxe-iscsi-boot?locale=en){:target="_blank"}
- [Debian Wiki: SAN/iSCSI/LIO](https://wiki.debian.org/SAN/iSCSI/LIO){:target="_blank"}
- [Red Hat: iSCSI root timeouts](https://docs.redhat.com/en/documentation/Red_Hat_Enterprise_Linux/6/html/storage_administration_guide/iscsi-root){:target="_blank"}
- [RFC 3721: iSCSI naming](https://datatracker.ietf.org/doc/rfc3721){:target="_blank"}
- [OPNsense docs: Dnsmasq DNS & DHCP](https://docs.opnsense.org/manual/dnsmasq.html){:target="_blank"}
