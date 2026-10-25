---
description: Migrate OPNsense from the end-of-life ISC DHCP server to Dnsmasq without losing static mappings or active leases. Covers ranges, host import, per-interface DNS options, lease takeover and rollback.
---

# OPNsense: Migrate from ISC DHCP to Dnsmasq

!!! info "AI-generated guide"
    This guide and the lease conversion script were written by an AI. I did not write the text myself. I did, however, carry out the procedure exactly as described on my production OPNsense 26.7 with five VLANs, 21 static mappings and 76 active leases, and verified the result afterwards.

ISC DHCP has been end-of-life since 2022. OPNsense still ships it (marked as `[legacy]` in the menu), but new installations use Dnsmasq since 25.7 and ISC will eventually move out of the core.

This guide migrates an existing multi-VLAN setup from ISC DHCPv4 to Dnsmasq. It also covers something most guides skip: taking over the **active leases**, so Dnsmasq knows which addresses are in use from the first second instead of waiting until every client has renewed.

## Why Dnsmasq and not Kea
OPNsense offers both. For a home or small office network Dnsmasq is probably the better fit:

| | Dnsmasq | Kea |
|---|---|---|
| OPNsense default for new installs | yes (since 25.7) | no |
| PXE / network boot options in the GUI | yes | no |
| Registers dynamic client names in DNS | yes | static reservations only |
| Dynamic IPv6 prefix tracking | yes | no |
| High availability / failover | no | yes |

Unless you need DHCP failover, pick Dnsmasq.

## Before you start
!!! note "Rollback is always possible"
    Disable Dnsmasq, re-enable ISC on all interfaces. Clients keep their leases until they expire, so there is no hard outage at any point of this migration.

- **Backup**: System → Configuration → Backups → Download configuration
- Work from a device with a static IP or a fixed DHCP assignment so you can always reach the GUI
- If you have IPv6 via SLAAC (Router Advertisements) and ISC DHCPv6 is **disabled**, IPv6 is not affected at all. Do not create IPv6 ranges in Dnsmasq.

## 1. Collect the ISC values
For every interface under Services → ISC DHCPv4 → [Interface], note:

| ISC field | Goes to |
|---|---|
| Range from / to | Dnsmasq → DHCP ranges |
| Additional Pools | one extra range each |
| DNS servers (if filled) | Dnsmasq → DHCP options, option 6 |
| DNS servers (empty) | means "system DNS", you have to set option 6 **explicitly** in Dnsmasq |
| Gateway (empty) | nothing, Dnsmasq defaults to the interface IP as well |
| Default lease time | Dnsmasq range → Lease time (empty = 86400 s) |
| NTP servers | option 42 |
| Static mappings | count them for the import check |

!!! tip "Interfaces without ISC config"
    The Dnsmasq interface dropdown lists every interface. Only select the ones that actually had an ISC instance.

## 2. Export the static mappings
Services → ISC DHCPv4 → [Interface] → download icon below the static mappings table.

The export is **one CSV per interface** with the columns `ip_address,hw_address,hostname,description`. Merge them into one file and check for:

- **Duplicate hostnames**: Dnsmasq registers names in DNS, give each host a unique name
- **Same MAC in several subnets** (e.g. a test VM): fine, Dnsmasq picks the entry matching the subnet, and the GUI import accepts it

## 3. Dnsmasq → General
Services → Dnsmasq DNS & DHCP → General, enable *advanced mode*.

| Setting | Value |
|---|---|
| Enable | **leave off** until step 7. Dnsmasq cannot bind port 67 while ISC is running |
| Interface | every interface that had ISC enabled |
| DNS → Listen port | `0` if another resolver (Pi-hole, Unbound, AdGuard) stays in charge. This disables the Dnsmasq DNS part completely |
| DHCP → DHCP FQDN | on |
| DHCP → DHCP default domain | shows your system domain, cannot be empty |
| DHCP → DHCP local domain | on |
| DHCP → DHCP authoritative | **on** (Dnsmasq is the only DHCP server) |
| DHCP → DHCP register firewall rules | on |
| DHCP → Router advertisements | off if radvd handles IPv6 |
| ISC / KEA DHCP (legacy) | all off |

Apply.

??? info "Authoritative and network boot"
    *Authoritative* means Dnsmasq answers requests for unknown leases instead of ignoring them. A TFTP server or a ProxyDHCP for PXE boot is **not** a second DHCP server, so this setting is correct even with network boot in place.

## 4. DHCP ranges
Tab *DHCP ranges*, one entry per interface. Leave *Subnet mask* on `automatic`, *Constructor* on `None`, *Tag* and *Domain* empty.

| Field | Value |
|---|---|
| Interface | the interface |
| Start / End address | the ISC range |
| Lease time | empty for the default, or your ISC value |
| Description | e.g. `LAN IPv4` |

Example for a typical setup:

| Interface | Start | End | Lease time |
|---|---|---|---|
| LAN | 192.168.1.150 | 192.168.1.254 | 86400 |
| IoT | 192.168.5.50 | 192.168.5.254 | 31536000 |
| Guest | 192.168.10.50 | 192.168.10.254 | 86400 |

??? info "Long lease times are no longer needed for stable IoT addresses"
    Under ISC a one-year lease is a common trick to keep IoT devices on the same address without creating a static mapping for every single one. Dnsmasq derives the offered address from a **hash of the MAC address**, so a device gets its old address again even after the lease expired and was forgotten. You can keep the long lease, but it now only controls how long a replaced device stays visible in the lease list.

## 5. Import the static mappings
Tab *Hosts* → upload icon (bottom right) → your merged CSV. Compare the row count, open two or three entries and check MAC, IP and hostname. Apply.

Reservations **outside** the dynamic range keep working as long as a range exists in the same subnet. You do not have to renumber anything.

## 6. DHCP options
Tab *DHCP options*, section *Options*. Type `Set`, Tag empty, Force off.

### DNS (option 6)
ISC used the system DNS servers when the field was empty. Dnsmasq does not do this reliably, so set it explicitly. If some networks use different resolvers (e.g. a dedicated Pi-hole for IoT), create one entry per interface:

| Interface | Option | Value |
|---|---|---|
| LAN | dns-server [6] | `192.168.1.3,192.168.1.4` |
| Guest | dns-server [6] | `192.168.1.3,192.168.1.4` |
| IoT | dns-server [6] | `192.168.1.6,192.168.1.7` |

### NTP (option 42)
One entry covers all networks:

| Interface | Option | Value |
|---|---|---|
| *(empty = all)* | ntp-server [42] | `0.0.0.0` |

!!! tip "0.0.0.0 means 'this interface'"
    Dnsmasq replaces `0.0.0.0` with the address of the interface the request came in on. Works for any option that takes an IP address. Under ISC you had to enter the interface IP on every single interface.

Apply.

## 7. Switch over and take over the active leases
Dnsmasq starts with an **empty lease table**. Without a takeover it would not know which addresses ISC has handed out until every client renews. With day-long leases that is fine, with year-long IoT leases it means months of blind spots in which Dnsmasq might offer an address that is actually in use (it pings first, but sleeping devices do not answer).

The script below converts the active ISC leases into the Dnsmasq lease file format. Nothing runs on the firewall itself, you only copy two files.

| # | Where | Action |
|---|---|---|
| 1 | GUI | Services → ISC DHCPv4 → [each interface]: untick *Enable* → Save |
| 2 | PC | `scp root@<opnsense>:/var/dhcpd/var/db/dhcpd.leases ./dhcpd.leases` |
| 3 | PC | `python3 isc2dnsmasq_leases.py --isc ./dhcpd.leases --out ./dnsmasq.leases --force` |
| 4 | PC | `scp ./dnsmasq.leases root@<opnsense>:/var/db/dnsmasq.leases` |
| 5 | GUI | Services → Dnsmasq DNS & DHCP → General → *Enable* → Save → Apply |
| 6 | GUI | Tab *Leases*: the imported leases show up immediately |

Do steps 1 to 5 in one go. Clients keep working on their existing leases in the meantime.

`--force` only skips the check for running `dnsmasq`/`dhcpd` processes, which is meant for running the script on the firewall itself. On your PC it would otherwise trip over a local dnsmasq from libvirt or NetworkManager.

!!! warning "Lease file path"
    OPNsense does not set `dhcp-leasefile`, so Dnsmasq uses the FreeBSD default `/var/db/dnsmasq.leases`. ISC runs chrooted, its lease file is `/var/dhcpd/var/db/dhcpd.leases`.

??? example "isc2dnsmasq_leases.py"
    What it does: keeps the last block per IP (ISC appends new states), takes only `binding state active`, skips leases expiring within 10 minutes, turns `ends never` into expiry `0` (infinite), strips domain parts from hostnames and writes `*` as client ID. Dnsmasq matches such leases by MAC and fills in the client ID on the first renewal. An existing output file is backed up first.

    ```python title="isc2dnsmasq_leases.py" linenums="1"
    #!/usr/bin/env python3
    """
    Convert active ISC dhcpd leases into a dnsmasq lease file.

    dnsmasq lease file format (one line per lease):
        <expiry-epoch> <mac> <ip> <hostname|*> <client-id|*>
    An expiry of 0 means "never expires".

    Usage:
        python3 isc2dnsmasq_leases.py --isc dhcpd.leases --out dnsmasq.leases --dry-run
        python3 isc2dnsmasq_leases.py --isc dhcpd.leases --out dnsmasq.leases --force
    """

    import argparse
    import os
    import re
    import subprocess
    import sys
    import time
    from datetime import datetime, timezone

    DEFAULT_ISC = "/var/dhcpd/var/db/dhcpd.leases"
    DEFAULT_OUT = "/var/db/dnsmasq.leases"

    HOSTNAME_RE = re.compile(r"[^A-Za-z0-9-]")


    def parse_isc_leases(path):
        """Return {ip: lease_dict} keeping the LAST block per IP (ISC appends)."""
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        leases = {}
        for match in re.finditer(r"lease\s+(\d+\.\d+\.\d+\.\d+)\s*\{(.*?)\n\}", text, re.S):
            ip, body = match.group(1), match.group(2)
            lease = {"ip": ip, "ends": None, "never": False, "state": None,
                     "mac": None, "hostname": None}

            m = re.search(r"^\s*ends\s+(never|\d\s+[\d/]+\s+[\d:]+);", body, re.M)
            if m:
                if m.group(1) == "never":
                    lease["never"] = True
                else:
                    _, date_s, time_s = m.group(1).split()
                    dt = datetime.strptime(f"{date_s} {time_s}", "%Y/%m/%d %H:%M:%S")
                    lease["ends"] = int(dt.replace(tzinfo=timezone.utc).timestamp())

            m = re.search(r"^\s*binding state\s+(\w+);", body, re.M)
            if m:
                lease["state"] = m.group(1)

            m = re.search(r"^\s*hardware ethernet\s+([0-9a-fA-F:]+);", body, re.M)
            if m:
                lease["mac"] = m.group(1).lower()

            m = re.search(r'^\s*client-hostname\s+"([^"]*)";', body, re.M)
            if m:
                lease["hostname"] = m.group(1)

            leases[ip] = lease
        return leases


    def sanitize_hostname(name):
        if not name:
            return "*"
        name = name.split(".")[0]
        name = HOSTNAME_RE.sub("-", name).strip("-")
        return name or "*"


    def process_running(name):
        try:
            subprocess.run(["pgrep", "-x", name], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False


    def main():
        ap = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
        ap.add_argument("--isc", default=DEFAULT_ISC, help="ISC dhcpd.leases path")
        ap.add_argument("--out", default=DEFAULT_OUT, help="dnsmasq lease file path")
        ap.add_argument("--dry-run", action="store_true", help="print result, write nothing")
        ap.add_argument("--min-remaining", type=int, default=600,
                        help="skip leases expiring within N seconds (default 600)")
        ap.add_argument("--force", action="store_true",
                        help="write even if dnsmasq or dhcpd is running")
        args = ap.parse_args()

        if not os.path.exists(args.isc):
            sys.exit(f"ERROR: ISC lease file not found: {args.isc}")

        now = int(time.time())
        all_leases = parse_isc_leases(args.isc)

        out_lines = []
        skipped = {"inactive": 0, "expired": 0, "no_mac": 0}
        for ip in sorted(all_leases, key=lambda s: tuple(int(o) for o in s.split("."))):
            l = all_leases[ip]
            if l["state"] != "active":
                skipped["inactive"] += 1
                continue
            if not l["mac"]:
                skipped["no_mac"] += 1
                continue
            if l["never"]:
                expiry = 0
            else:
                if l["ends"] is None or l["ends"] - now < args.min_remaining:
                    skipped["expired"] += 1
                    continue
                expiry = l["ends"]
            out_lines.append(f"{expiry} {l['mac']} {ip} {sanitize_hostname(l['hostname'])} *")

        print(f"Parsed {len(all_leases)} lease blocks from {args.isc}")
        print(f"Active leases to import: {len(out_lines)}")
        print(f"Skipped: {skipped['inactive']} inactive, {skipped['expired']} expired/short, "
              f"{skipped['no_mac']} without MAC")
        print("-" * 60)
        for line in out_lines:
            print(line)
        print("-" * 60)

        if args.dry_run:
            print("Dry run, nothing written.")
            return

        if not args.force:
            if process_running("dnsmasq"):
                sys.exit("ERROR: dnsmasq is running. Disable it first or use --force.")
            if process_running("dhcpd"):
                sys.exit("ERROR: ISC dhcpd is still running, leases may still change. "
                         "Disable ISC DHCPv4 on all interfaces first or use --force.")

        if os.path.exists(args.out):
            backup = f"{args.out}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
            os.replace(args.out, backup)
            print(f"Existing lease file moved to {backup}")

        tmp = args.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out_lines) + ("\n" if out_lines else ""))
        os.chmod(tmp, 0o644)
        os.replace(tmp, args.out)
        print(f"Wrote {len(out_lines)} leases to {args.out}")


    if __name__ == "__main__":
        main()
    ```

## 8. Verify
1. Renew a lease on a client:
```bash
nmcli con down "<connection>" && nmcli con up "<connection>"
```
2. Check address, gateway and DNS:
```bash
nmcli dev show | grep -E 'IP4.ADDRESS|IP4.GATEWAY|IP4.DNS'
```
3. A client with a fixed assignment shows up in the *Leases* tab with Lease Type `static`.
4. Over the next days, confirm that IoT devices keep their addresses after a reboot.

Side effect you will probably notice: reconnects are a lot faster. ISC syncs its lease file on every transaction and hooks into other services, Dnsmasq answers known clients straight from memory.

## Rollback
1. Dnsmasq → General → *Enable* off → Apply
2. ISC DHCPv4 → *Enable* on every interface → Save
3. Read Services → Dnsmasq DNS & DHCP → Log File, fix the cause, try again from step 7

## Afterwards
- **ISC stays installed**: as of 26.7 it is still part of the OPNsense core and cannot be uninstalled. Disabled on all interfaces, `dhcpd` simply does not run. When a future release moves it to a plugin, do not install that plugin.
- **Local hostname resolution**: with the Dnsmasq DNS part disabled, your resolver does not know the DHCP client names. If you want that, enable Dnsmasq DNS on a side port (e.g. `53053`, not `5353` which is mDNS) and forward your local domain from Pi-hole/Unbound to `127.0.0.1:53053`.
- **Network boot**: Dnsmasq has the PXE options in the GUI (*DHCP boot*, *DHCP tags*). A TFTP server next to it is enough, no second DHCP server needed.

## Sources
- [OPNsense docs: Dnsmasq DNS & DHCP](https://docs.opnsense.org/manual/dnsmasq.html){:target="_blank"}
- [opnsense/core #9155: Move ISC DHCP to plugins](https://github.com/opnsense/core/issues/9155){:target="_blank"}
- [Home Network Guy: Migrate from ISC DHCP to dnsmasq or Kea](https://homenetworkguy.com/how-to/migrate-from-isc-dhcp-to-dnsmasq-or-kea-dhcp-in-opnsense/){:target="_blank"}
- [dnsmasq-discuss: why addresses are allocated by MAC hash](https://lists.thekelleys.org.uk/pipermail/dnsmasq-discuss/2010q2/003884.html){:target="_blank"}
