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
* Handle blade GPU expansions
* Automatic cabling (server's interface to switch's interface) using lldp
* Local inventory using `Inventory Item` for CPU, GPU, RAM, RAID cards, physical disks (behind raid cards)
* PSUs creation and power consumption reporting (based on vendor's tools)
* Associate hypervisor devices to the virtualization cluster
* Associate virtual machines to the hypervisor device

# Requirements

- Netbox >= 3.7
- Python >= 3.8
- [pynetbox](https://github.com/digitalocean/pynetbox/)
- [python3-netaddr](https://github.com/drkjam/netaddr)
- [python3-netifaces](https://github.com/al45tair/netifaces)
- [jsonargparse](https://github.com/omni-us/jsonargparse/)

- ethtool
- dmidecode
- ipmitool
- lldpd
- lshw

## Inventory requirement
- hpassacli
- storcli
- omreport

# Installation

```
# pip3 install netbox-agent
```

# Usage

The agent can be run from a shell and get its configuration from either the configuration file or environment variables.

Configuration values are overridden based on the following precedence: command line arguments (might include config file) > environment variables > default config file > defaults.

```
# netbox_agent -c /etc/netbox_agent.yaml --register
INFO:root:Creating chassis blade (serial: QTFCQ574502EF)
INFO:root:Creating blade (serial: QTFCQ574502D2) myserver on chassis QTFCQ574502EF
INFO:root:Setting device (QTFCQ574502D2) new slot on Slot 9 (Chassis QTFCQ574502EF)..
INFO:root:Interface a8:1e:84:f2:9e:6a not found, creating..
INFO:root:Creating NIC enp1s0f1 (a8:1e:84:f2:9e:6a) on myserver
INFO:root:Interface 02:42:7a:89:cf:a4 not found, creating..
INFO:root:Creating NIC br-07ea1e4a2f0e (02:42:7a:89:cf:a4) on myserver
INFO:root:Create new IP 172.19.0.1/16 on br-07ea1e4a2f0e
INFO:root:Interface a8:1e:84:f2:9e:69 not found, creating..
INFO:root:Creating NIC enp1s0f0 (a8:1e:84:f2:9e:69) on myserver
INFO:root:Create new IP 42.42.42.42/24 on enp1s0f0
INFO:root:Create new IP fe80::aa1e:84ff:fef2:9e69/64 on enp1s0f0
INFO:root:Interface a8:1e:84:cd:9d:d6 not found, creating..
INFO:root:Creating NIC IPMI (a8:1e:84:cd:9d:d6) on myserver
INFO:root:Create new IP 10.191.122.10/24 on IPMI
```

If you need, you can update only specific informations like:
* Network
* Inventory
* Location
* PSUs

```
# ip a add 42.42.42.43/24 dev enp1s0f1
# netbox_agent -c /etc/netbox_agent.yaml --update-network
INFO:root:Create new IP 42.42.42.43/24 on enp1s0f1
# netbox_agent --update-inventory
INFO:root:Creating Disk Samsung SSD 850 S2RBNX0K101698D
```

# Configuration

```
# Netbox configuration
netbox:
 url: 'http://netbox.internal.company.com'
 token: supersecrettoken
 # uncomment to disable ssl verification
 # ssl_verify: false
 # uncomment to use the system's CA certificates
 # ssl_ca_certs_file: /etc/ssl/certs/ca-certificates.crt

# Network configuration
network:
  # Regex to ignore interfaces
  ignore_interfaces: "(dummy.*|docker.*)"
  # Regex to ignore IP addresses
  ignore_ips: (127\.0\.0\..*)
  # enable auto-cabling by parsing LLDP answers
  lldp: true

#
# You can use these to change the Netbox roles.
# These are the defaults.
#
#device:
# chassis_role: "Server Chassis"
# blade_role: "Blade"
# server_role: "Server"
# tags: server, blade, ,just a comma,delimited,list
# custom_fields: field1=value1,field2=value2#
#
# Can use this to set the tenant
#
#tenant:
# driver: "file:/tmp/tenant"
# regex: "(.*)"

## Enable virtual machine support
# virtual:
#   # not mandatory, can be guessed
#   enabled: True
#   # see https://netbox.company.com/virtualization/clusters/
#   cluster_name: my_vm_cluster

## Enable hypervisor support
# virtual:
#   enabled: false
#   hypervisor: true
#   cluster_name: my_cluster
#   list_guests_cmd: command that lists VMs names

# Enable datacenter location feature in Netbox
datacenter_location:
 driver: "cmd:cat /etc/qualification | tr [A-Z] [a-z]"
 regex: "datacenter: (?P<datacenter>[A-Za-z0-9]+)"
# driver: 'cmd:lldpctl'
# regex: 'SysName: .*\.([A-Za-z0-9]+)'
#
# driver: "file:/tmp/datacenter"
# regex: "(.*)"

# Enable rack location feature in Netbox
rack_location:
# driver: 'cmd:lldpctl'
# match SysName: sw-dist-a1.dc42
# regex: 'SysName:[ ]+[A-Za-z]+-[A-Za-z]+-([A-Za-z0-9]+)'
#
# driver: "file:/tmp/datacenter"
# regex: "(.*)"

# Enable local inventory reporting
inventory: true
```

# Specific workflow

## Blades

Each vendor class has a `is_blade` method which is later used for `Device` creation using the Netbox [parent/child feature](https://netbox.readthedocs.io/en/stable/core-functionality/devices/).

The `get_blade_slot` method return the name of the `Device Bay`.


Certain vendors don't report the blade slot in `dmidecode`, so we can use the `slot_location` regex feature of the configuration file.

Some blade servers can be equipped with additional hardware using expansion blades, next to the processing blade, such as GPU expansion, or drives bay expansion. By default, the hardware from the expnasion is associated with the blade server itself, but it's possible to register the expansion as its own device using the `--expansion-as-device` command line parameter, or by setting `expansion_as_device` to `true` in the configuration file.

## Drives attributes processing

It is possible to process drives extended attributes such as the drive's physical or logical identifier, logical drive RAID type, size, consistency and so on.

Those attributes as set as `custom_fields` in Netbox, and need to be registered properly before being able to specify them during the inventory phase.

As the custom fields have to be created prior being able to register the disks extended attributes, this feature is only activated using the `--process-virtual-drives` command line parameter, or by setting `process_virtual_drives` to `true` in the configuration file.

The custom fields to create as `DCIM > inventory item` `Text` are described below.

```
NAME            LABEL                      DESCRIPTION
mount_point     Mount point                Device mount point(s)
pd_identifier   Physical disk identifier   Physical disk identifier in the RAID controller
vd_array        Virtual drive array        Virtual drive array the disk is member of
vd_consistency  Virtual drive consistency  Virtual disk array consistency
vd_device       Virtual drive device       Virtual drive system device
vd_raid_type    Virtual drive RAID         Virtual drive array RAID type
vd_size         Virtual drive size         Virtual drive array size
```

In the current implementation, the disks attributes ore not updated: if a disk with the correct serial number is found, it's sufficient to consider it as up to date.

To force the reprocessing of the disks extended attributes, the `--force-disk-refresh` command line option can be used: it removes all existing disks to before populating them with the correct parsing. Unless this option is specified, the extended attributes won't be modified unless a disk is replaced.

It is possible to dump the physical/virtual disks map on the filesystem under the JSON notation to ease or automate disks management. The file path has to be provided using the `--dump-disks-map` command line parameter.


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

## [Dell Inc.](https://github.com/Solvik/netbox-agent/blob/master/netbox_agent/vendors/dell.py)

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

## [HP / HPE](https://github.com/Solvik/netbox-agent/blob/master/netbox_agent/vendors/hp.py)

### Blades

* HP BladeSystem c7000 Enclosure G2 / G3 (your `DeviceType` should have slots named `Bay 1` and so on)
* HP ProLiant BL460c Gen8
* HP ProLiant BL460c Gen9
* HP ProLiant BL460c Gen10
* HP ProLiant BL460c Gen10 Graphics Exp its expansion HP ProLiant BL460c Graphics Expansion Blade
* HP Moonshot 1500 Enclosure (your `DeviceType` should have slots batch create with `Bay c[1-45n1]`) with HP ProLiant m750, m710x, m510 Server Cartridge

### Pizzas

* ProLiant DL380p Gen8
* ProLiant SL4540 Gen8
* ProLiant SL4540 Gen9
* ProLiant XL450 Gen10

## [Supermicro](https://github.com/Solvik/netbox-agent/blob/master/netbox_agent/vendors/supermicro.py)

### Blades

* SBI-* and SBA-* should be supported, but I need dmidecode output example to support automatic blade location

### Pizzas

* SSG-6028R
* SYS-6018R

## [QCT](https://github.com/Solvik/netbox-agent/blob/master/netbox_agent/vendors/qct.py)

### Blades

* QuantaMicro X10E-9N

### Pizzas

* Nothing ATM, feel free to send me a dmidecode or make a PR!

# Known limitations

* The project is only compatible with Linux.
Since it uses `ethtool` and parses `/sys/` directory, it's not compatible with *BSD distributions.
* Netbox `>=2.6.0,<=2.6.2` has a caching problem ; if the cache lifetime is too high, the script can get stale data after modification.
We advise to set `CACHE_TIME` to `0`.

# Developing

If you want to run the agent while adding features or just for debugging purposes

```
# git clone https://github.com/Solvik/netbox-agent.git
# cd netbox-agent
# python3 -m netbox_agent.cli --register
```

On a personal note, I use the docker image from [netbox-community/netbox-docker](https://github.com/netbox-community/netbox-docker)
```
# git clone https://github.com/netbox-community/netbox-docker
# cd netbox-docker
# docker-compose pull
# docker-compose up
```

For the linter and code formatting, you need to run:
```
ruff check
ruff format
```
