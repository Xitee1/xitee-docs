---
description: Guide to setting up LUKS disk encryption with a USB stick as the unlock key, including automatic boot unlocking and LUKS header backups.
---

# Disk encryption with LUKS and using USB stick to unlock

!!! danger "Danger!"
    Make sure to **always** replace `/dev/sdX` with the correct disk.
    Using the wrong path can and likely will cause data loss!

### Creating a new USB key

1. Execute `lsblk` and find the path of your usb drive (e.g. `/dev/sdb`)
2. Make new label:
```bash
sudo parted /dev/sdX "mklabel gpt"
```
```
yes
```
3. Make partitions:
```bash
sudo cfdisk /dev/sdX
```
```
new - enter
enter
type - enter
    Linux Filesystem - enter
write - enter
yes - enter
quit - enter
```
4. Formatting:
```bash
sudo mkfs.ext4 /dev/sdX
```
```
y
```
5. Generate key and write it to usb stick:
```bash
sudo dd if=/dev/urandom of=/dev/sdX bs=512 seek=1 count=2046 
```
6. Proceed with [Extracting a bin key file from USB key](#extracting-a-bin-key-file-from-usb-key) and then [Adding a bin key file to a disk](#adding-a-bin-key-file-to-a-disk)

### Extracting a bin key file from USB key
`dd if=/dev/sdX bs=512 skip=1 count=16 of=recoveredKeyFile.bin`

### Adding a bin key file to a disk
`cryptsetup luksAddKey /dev/sdX keyFile.bin`

### Automatic unlocking on boot (by plugging in USB key on boot)

Configure crypttab (example, replace with your values, see table below):
!!! note
    When having multiple disks, you must increment the `sda-crypt` alphabetically.
```crypttab title="/etc/crypttab"
sda-crypt UUID=65fc9547-361c-40dd-bf45-d26828c5ae0d /dev/disk/by-id/usb-Verbatim_STORE_N_GO_12073991000507-0:0 luks,tries=3,keyfile-size=8192,keyfile-offset=512
```


| Option              | Description                                                                       |
| ------------------- | --------------------------------------------------------------------------------- |
| UUID                | UUID of encrypted disk, find out using `blkid \| grep crypto_LUKS`                |
| /dev/disk/by-id/xxx | Name / ID of USB stick used for unlocking, find out using `ls -l /dev/disk/by-id` |

## Backup LUKS header
`cryptsetup luksHeaderBackup /dev/sdX --header-backup-file DATA_HDD_2.luks.bin`

## Sources
- [https://knilix.home.blog/luks-encryption/](https://knilix.home.blog/luks-encryption/) (german)