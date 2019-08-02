
Netbox agent
===========

This project aims to create hardware automatically into Netbox based on standard tools (dmidecode, lldpd, parsing /sys/, etc).
The goal is to generate an existing infrastructure on Netbox and have the ability to update it regularly.

Hardware
==
Tested on:

Dell Inc.
----------

Blades
--
* PowerEdge M1000e
* PowerEdge M640
* PowerEdge M630
* PowerEdge M620
* PowerEdge M610

Pizzas
--
* DSS7500

HP
---
- WIP

HPE
---
- WIP

TODO
===
- [ ] HP(E) servers support
- [ ] Handle blade moving
- [ ] Handle network cards (MAC, IP addresses)
- [ ] Handle switch <> NIC connections (using lldp)
- [ ] Handle blade and server local changes (new NIC, new RAM, etc) using somekind of diff

Ideas
===

- [ ] CPU, RAID Card(s), RAM, Disks in `Device`'s `Inventory`
- [ ] `CustomFields` support with firmware versions for Device (BIOS), RAID Cards and disks
- [ ] Handle custom business logic : datacenter guessing logic based on hostname/switch name
