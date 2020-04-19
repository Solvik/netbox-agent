# Netbox agent [![Build Status](https://travis-ci.com/Solvik/netbox-agent.svg?branch=master)](https://travis-ci.com/Solvik/netbox-agent)

This project aims to create hardware automatically into [Netbox](https://github.com/netbox-community/netbox) based on standard tools (dmidecode, lldpd, parsing /sys/, etc).

The goal is to generate an existing infrastructure on Netbox and have the ability to update it regularly by executing the agent.

# Features

* Create virtual machines, servers, chassis and blade through standard tools (`dmidecode`)
* Create physical, bonding and vlan network interfaces with IPs (IPv4 & IPv6)
* Create IPMI interface if found
* Create or get existing VLAN and associate it to interfaces
* Generic ability to guess datacenters and rack location through drivers (`cmd` and `file` and custom ones)
* Update existing `Device` and `Interface`
* Handle blade moving (new slot, new chassis)
* Automatic cabling (server's interface to switch's interface) using lldp
* Local inventory using `Inventory Item` for CPU, RAM, RAID cards, physical disks (behind raid cards)
* PSUs creation and power consumption reporting (based on vendor's tools)

# Requirements

- Netbox >= 2.6
- Python >= 3.4
- [pynetbox](https://github.com/digitalocean/pynetbox/)
- [python3-netaddr](https://github.com/drkjam/netaddr)
- [python3-netifaces](https://github.com/al45tair/netifaces)
- [jsonargparse](https://github.com/omni-us/jsonargparse/)

- ethtool
- dmidecode
- ipmitool
- lldpd
- lshw

# Known limitations

* The project is only compatible with Linux.
Since it uses `ethtool` and parses `/sys/` directory, it's not compatible with *BSD distributions.
* Netbox `>=2.6.0,<=2.6.2` has a caching problem ; if the cache lifetime is too high, the script can get stale data after modification.
We advise to set `CACHE_TIME` to `0`.

# Configuration

```
netbox:
 url: 'http://netbox.internal.company.com'
 token: supersecrettoken

network:
  ignore_interfaces: "(dummy.*|docker.*)"
  ignore_ips: (127\.0\.0\..*)
  # enable auto-cabling
  lldp: true

# virtual:
#   # not mandatory, can be guessed
#   enabled: True
#   # see https://netbox.company.com/virtualization/clusters/
#   cluster_name: my_vm_cluster

datacenter_location:
 driver: "cmd:cat /etc/qualification | tr [a-z] [A-Z]"
 regex: "DATACENTER: (?P<datacenter>[A-Za-z0-9]+)"
# driver: 'cmd:lldpctl'
# regex: 'SysName: .*\.([A-Za-z0-9]+)'
#
# driver: "file:/tmp/datacenter"
# regex: "(.*)"

rack_location:
# driver: 'cmd:lldpctl'
# match SysName: sw-dist-a1.dc42
# regex: 'SysName:[ ]+[A-Za-z]+-[A-Za-z]+-([A-Za-z0-9]+)'
#
# driver: "file:/tmp/datacenter"
# regex: "(.*)"

inventory: true
```

# Specific workflow

## Blades

Each vendor class has a `is_blade` method which is later used for `Device` creation using the Netbox [parent/child feature](https://netbox.readthedocs.io/en/stable/core-functionality/devices/).

The `get_blade_slot` method return the name of the `Device Bay`.


Certain vendors don't report the blade slot in `dmidecode`, so we can use the `slot_location` regex feature of the configuration file.

## Anycast IP

The default behavior of the agent is to assign an interface to an IP.
So two servers with anycasted IPs, running update mode, would only trigger IP's interface assignement in a loop.

In order to handle this case, user need to set Netbox IP's mode to `Anycast` so that the agent will create another one if it's present on another server.

# Hardware

Tested on:

## Virtual Machines

* Hyper-V
* VMWare
* VirtualBox
* AWS
* GCP

## Dell Inc.

### Blades

* PowerEdge MX7000
* PowerEdge M1000e (your `DeviceType` should have slots named `Slot 01` and so on)
* PowerEdge MX740c
* PowerEdge M640
* PowerEdge M630
* PowerEdge M620
* PowerEdge M610

### Pizzas

* DSS7500

## HP / HPE

### Blades

* HP BladeSystem c7000 Enclosure G2 / G3 (your `DeviceType` should have slots named `Bay 1` and so on)
* HP ProLiant BL460c Gen8
* HP ProLiant BL460c Gen9
* HP ProLiant BL460c Gen10

### Pizzas

* ProLiant DL380p Gen8
* ProLiant SL4540 Gen8
* ProLiant SL4540 Gen9
* ProLiant XL450 Gen10

## Supermicro

### Blades

Feel free to send me a dmidecode output for Supermicro's blade!

### Pizzas

* SSG-6028R
* SYS-6018R

## QCT

### Blades

* QuantaMicro X10E-9N

### Pizzas

* Nothing ATM, feel free to send me a dmidecode or make a PR!

# TODO

- [ ] `CustomFields` support with firmware versions for Device (BIOS), RAID Cards and disks
