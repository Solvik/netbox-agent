# Netbox agent


This project aims to create hardware automatically into [Netbox](https://github.com/netbox-community/netbox) based on standard tools (dmidecode, lldpd, parsing /sys/, etc).

The goal is to generate an existing infrastructure on Netbox and have the ability to update it regularly by executing the agent.

# Features

* Create servers, chassis and blade through standard tools (`dmidecode`)
* Create physical network interfaces with IPs
* Generic ability to guess datacenters and rack location through drivers (`cmd` and `file` and custom ones)
* Update existing `Device` and `Interfaces`
* Handle blade moving (new slot, new chassis)

# Known limitations

* The project is only compatible with Linux.
Since it uses `ethtool` and parses `/sys/` directory, it's not compatible with *BSD distributions.
* Netbox `>=2.6.0,<=2.6.2` has a caching problem ; if the cache lifetime is too high, the script can get stale data after modification.

# Configuration

```
netbox:
 url: 'http://netbox.internal.company.com'
 token: supersecrettoken

datacenter_location:
 # driver_file: /opt/netbox_driver_dc.py
 driver: file:/etc/qualification
 regex: "datacenter: (?P<datacenter>[A-Za-z0-9]+)"
# driver: 'cmd:lldpctl'
# regex = 'SysName: .*\.(?P<datacenter>[A-Za-z0-9]+)'```
```

# Hardware

Tested on:

## Dell Inc.

### Blades

* PowerEdge M1000e
* PowerEdge M640
* PowerEdge M630
* PowerEdge M620
* PowerEdge M610

### Pizzas

* DSS7500

## HP

### Blades

* HP BladeSystem c7000 Enclosure G2
* HP ProLiant BL460c Gen8
* HP ProLiant BL460c Gen9

### Pizzas

* ProLiant DL380p Gen8

## HPE

* HPE ProLiant XL450 Gen10

# TODO

- [ ] Handle switch <> NIC connections (using lldp)
- [ ] CPU, RAID Card(s), RAM, Disks in `Device`'s `Inventory`
- [ ] `CustomFields` support with firmware versions for Device (BIOS), RAID Cards and disks
