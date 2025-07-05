import logging
import os
import re
import glob
import sys 
from itertools import chain, islice
from pathlib import Path

import netifaces
import subprocess
from netaddr import IPAddress
from packaging import version

from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.ethtool import Ethtool
from netbox_agent.ipmi import IPMI
from netbox_agent.lldp import LLDP
from netbox_agent.misc import is_tool,get_fqdn

VIRTUAL_NET_FOLDER = Path("/sys/devices/virtual/net")

def _execute_brctl_cmd(interface_name):
    if not is_tool("brctl"):
        logging.error(
            "Brctl does not seem to be present on your system. Add it your path or "
            "check the compatibility of this project with your distro."
        )
        sys.exit(1)
    return subprocess.getoutput(
            "brctl show " + str(interface_name)
            )

def _execute_basename_cmd(interface_name):
    parent_int = None
    parent_list = glob.glob("/sys/class/net/" + str(interface_name) + "/lower_*")
    if len(parent_list)>0:
        parent_int = os.path.basename(parent_list[0]).split("_")[1]
    return parent_int

class Network(object):
    def __init__(self, server, *args, **kwargs):
        self.nics = []

        self.server = server
        self.tenant = self.server.get_netbox_tenant()

        self.lldp = LLDP() if config.network.lldp else None
        self.nics = self.scan()
        self.ipmi = None
        self.dcim_choices = {}
        dcim_c = nb.dcim.interfaces.choices()
        for _choice_type in dcim_c:
            key = "interface:{}".format(_choice_type)
            self.dcim_choices[key] = {}
            for choice in dcim_c[_choice_type]:
                self.dcim_choices[key][choice["display_name"]] = choice["value"]

        self.ipam_choices = {}
        ipam_c = nb.ipam.ip_addresses.choices()
        for _choice_type in ipam_c:
            key = "ip-address:{}".format(_choice_type)
            self.ipam_choices[key] = {}
            for choice in ipam_c[_choice_type]:
                self.ipam_choices[key][choice["display_name"]] = choice["value"]

    def get_network_type():
        return NotImplementedError

    def scan(self):
        nics = []
        for interface in os.listdir("/sys/class/net/"):
            # ignore if it's not a link (ie: bonding_masters etc)
            if not os.path.islink("/sys/class/net/{}".format(interface)):
                continue

            if config.network.ignore_interfaces and re.match(
                config.network.ignore_interfaces, interface
            ):
                logging.debug("Ignore interface {interface}".format(interface=interface))
                continue

            ip_addr = netifaces.ifaddresses(interface).get(netifaces.AF_INET, [])
            ip6_addr = netifaces.ifaddresses(interface).get(netifaces.AF_INET6, [])
            if config.network.ignore_ips:
                for i, ip in enumerate(ip_addr):
                    if re.match(config.network.ignore_ips, ip["addr"]):
                        ip_addr.pop(i)
                for i, ip in enumerate(ip6_addr):
                    if re.match(config.network.ignore_ips, ip["addr"]):
                        ip6_addr.pop(i)

            # netifaces returns a ipv6 netmask that netaddr does not understand.
            # this strips the netmask down to the correct format for netaddr,
            # and remove the interface.
            # ie, this:
            #   {
            #      'addr': 'fe80::ec4:7aff:fe59:ec4a%eno1.50',
            #      'netmask': 'ffff:ffff:ffff:ffff::/64'
            #   }
            #
            # becomes:
            #   {
            #      'addr': 'fe80::ec4:7aff:fe59:ec4a',
            #      'netmask': 'ffff:ffff:ffff:ffff::'
            #   }
            #
            for addr in ip6_addr:
                addr["addr"] = addr["addr"].replace("%{}".format(interface), "")
                addr["mask"] = addr["mask"].split("/")[0]
                ip_addr.append(addr)

            ethtool = Ethtool(interface).parse()
            if (
                config.network.primary_mac == "permanent"
                and ethtool
                and ethtool.get("mac_address")
            ):
                mac = ethtool["mac_address"]
            else:
                mac = open("/sys/class/net/{}/address".format(interface), "r").read().strip()
                if mac == "00:00:00:00:00:00":
                    mac = None
            if mac:
                mac = mac.upper()

            mtu = int(open("/sys/class/net/{}/mtu".format(interface), "r").read().strip())
            vlan = None
            if len(interface.split(".")) > 1:
                vlan = int(interface.split(".")[1])

            virtual = Path(f"/sys/class/net/{interface}").resolve().parent == VIRTUAL_NET_FOLDER

            bonding = False
            bonding_slaves = []
            if os.path.isdir("/sys/class/net/{}/bonding".format(interface)):
                bonding = True
                virtual = False
                bonding_slaves = (
                    open("/sys/class/net/{}/bonding/slaves".format(interface)).read().split()
                )

            bridging = False
            bridge_parents = []
            outputbrctl = _execute_brctl_cmd(interface)
            lineparse_output = outputbrctl.splitlines()
            if len(lineparse_output)>1:
                headers = lineparse_output[0].replace("\t\t", "\t").split("\t")
                brctl = dict((key, []) for key in headers)
                # Interface is a bridge
                bridging = True
                virtual = False
                for spec_line in lineparse_output[1:]:
                    cleaned_spec_line = spec_line.replace("\t\t\t\t\t\t\t", "\t\t\t\t\t\t")
                    cleaned_spec_line = cleaned_spec_line.replace("\t\t", "\t").split("\t")
                    for col, val in enumerate(cleaned_spec_line):
                        if val:
                            brctl[headers[col]].append(val)

                bridge_parents = brctl[headers[-1]]

            parent = None
            if virtual:
                parent = _execute_basename_cmd(interface)
                if not parent:
                    parent = None
            nic = {
                "name": interface,
                "mac": mac,
                "ip": [
                    "{}/{}".format(x["addr"], IPAddress(x["mask"]).netmask_bits()) for x in ip_addr
                ]
                if ip_addr
                else None,  # FIXME: handle IPv6 addresses
                "ethtool": ethtool,
                "virtual": virtual,
                "vlan": vlan,
                "mtu": mtu,
                "bonding": bonding,
                "bonding_slaves": bonding_slaves,
                "parent": parent,
                "bridged": bridging,
                "bridge_parents": bridge_parents
            }
            nics.append(nic)
        return nics

    def _set_bonding_interfaces(self):
        bonding_nics = (x for x in self.nics if x["bonding"])
        for nic in bonding_nics:
            bond_int = self.get_netbox_network_card(nic)
            logging.debug("Setting slave interface for {name}".format(name=bond_int.name))
            for slave_int in (
                self.get_netbox_network_card(slave_nic)
                for slave_nic in self.nics
                if slave_nic["name"] in nic["bonding_slaves"]
            ):
                if slave_int.lag is None or slave_int.lag.id != bond_int.id:
                    logging.debug(
                        "Settting interface {name} as slave of {master}".format(
                            name=slave_int.name, master=bond_int.name
                        )
                    )
                    slave_int.lag = bond_int
                    slave_int.save()
        else:
            return False
        return True

    def _set_bridged_interfaces(self):
        bridged_nics = (x for x in self.nics if x["bridged"])
        for nic in bridged_nics:
            bridged_int = self.get_netbox_network_card(nic)
            logging.debug("Setting bridge interface and properties for {name}".format(name=bridged_int.name))
            bridged_int.type = "bridge"
            for parent_int in (
                self.get_netbox_network_card(parent_bridge_nic)
                for parent_bridge_nic in self.nics
                if parent_bridge_nic["name"] in nic["bridge_parents"]
            ):
                logging.debug(
                    "Setting interface {parent} as a bridge to {name}".format(
                        name=bridged_int.name, parent=parent_int.name
                    )
                )
                parent_int.bridge = bridged_int
                parent_int.save()
            bridged_int.bridge = {"name": parent_int.name, "id": parent_int.id} 
            bridged_int.save()
        else:
            return False
        return True

    def get_network_cards(self):
        return self.nics

    def get_netbox_network_card(self, nic):
        if config.network.nic_id == "mac" and nic["mac"]:
            interface = self.nb_net.interfaces.get(mac_address=nic["mac"], **self.custom_arg_id)
        else:
            interface = self.nb_net.interfaces.get(name=nic["name"], **self.custom_arg_id)
        return interface

    def get_netbox_network_cards(self):
        return self.nb_net.interfaces.filter(**self.custom_arg_id)

    def get_netbox_type_for_nic(self, nic):
        if self.get_network_type() == "virtual":
            return self.dcim_choices["interface:type"]["Virtual"]

        if nic.get("bonding"):
            return self.dcim_choices["interface:type"]["Link Aggregation Group (LAG)"]

        if nic.get("virtual"):
            return self.dcim_choices["interface:type"]["Virtual"]

        if nic.get("bridge"):
            return self.dcim_choices["interface:type"]["Bridge"]

        if nic.get("ethtool") is None:
            return self.dcim_choices["interface:type"]["Other"]

        max_speed = nic["ethtool"]["max_speed"]
        if max_speed == "-":
            max_speed = nic["ethtool"]["speed"]

        if max_speed == "10000Mb/s":
            if nic["ethtool"]["port"] in ("FIBRE", "Direct Attach Copper"):
                return self.dcim_choices["interface:type"]["SFP+ (10GE)"]
            return self.dcim_choices["interface:type"]["10GBASE-T (10GE)"]

        elif max_speed == "25000Mb/s":
            if nic["ethtool"]["port"] in ("FIBRE", "Direct Attach Copper"):
                return self.dcim_choices["interface:type"]["SFP28 (25GE)"]

        elif max_speed == "5000Mb/s":
            return self.dcim_choices["interface:type"]["5GBASE-T (5GE)"]

        elif max_speed == "2500Mb/s":
            return self.dcim_choices["interface:type"]["2.5GBASE-T (2.5GE)"]

        elif max_speed == "1000Mb/s":
            if nic["ethtool"]["port"] in ("FIBRE", "Direct Attach Copper"):
                return self.dcim_choices["interface:type"]["SFP (1GE)"]
            return self.dcim_choices["interface:type"]["1000BASE-T (1GE)"]

        return self.dcim_choices["interface:type"]["Other"]

    def get_or_create_vlan(self, vlan_id):
        # FIXME: we may need to specify the datacenter
        # since users may have same vlan id in multiple dc
        vlan = nb.ipam.vlans.get(
            vid=vlan_id,
        )
        if vlan is None:
            vlan = nb.ipam.vlans.create(
                name="VLAN {}".format(vlan_id),
                vid=vlan_id,
            )
        return vlan

    def get_vrf_id(self, vrf_name):
        vrf = nb.ipam.vrfs.get(name=vrf_name, **self.custom_arg_id)
        if vrf:
            return vrf.id
        else: 
            return None

    def reset_vlan_on_interface(self, nic, interface):
        update = False
        vlan_id = nic["vlan"]
        lldp_vlan = (
            self.lldp.get_switch_vlan(nic["name"])
            if config.network.lldp and isinstance(self, ServerNetwork)
            else None
        )
        # For strange reason, we need to get the object from scratch
        # The object returned by pynetbox's save isn't always working (since pynetbox 6)
        interface = self.nb_net.interfaces.get(id=interface.id)

        # Handle the case were the local interface isn't an interface vlan as reported by Netbox
        # and that LLDP doesn't report a vlan-id
        if (
            vlan_id is None
            and lldp_vlan is None
            and (interface.mode is not None or len(interface.tagged_vlans) > 0)
        ):
            logging.info(
                "Interface {interface} is not tagged, reseting mode".format(interface=interface)
            )
            update = True
            interface.mode = None
            interface.tagged_vlans = []
            interface.untagged_vlan = None
        # if the local interface is configured with a vlan, it's supposed to be taggued
        # if mode is either not set or not correctly configured or vlan are not
        # correctly configured, we reset the vlan
        elif vlan_id and (
            interface.mode is None
            or type(interface.mode) is not int
            and (
                hasattr(interface.mode, "value")
                and interface.mode.value == self.dcim_choices["interface:mode"]["Access"]
                or len(interface.tagged_vlans) != 1
                or int(interface.tagged_vlans[0].vid) != int(vlan_id)
            )
        ):
            logging.info(
                "Resetting tagged VLAN(s) on interface {interface}".format(interface=interface)
            )
            update = True
            nb_vlan = self.get_or_create_vlan(vlan_id)
            interface.mode = self.dcim_choices["interface:mode"]["Tagged"]
            interface.tagged_vlans = [nb_vlan] if nb_vlan else []
            interface.untagged_vlan = None
        # Finally if LLDP reports a vlan-id with the pvid attribute
        elif lldp_vlan:
            pvid_vlan = [
                key for (key, value) in lldp_vlan.items() if "pvid" in value and value["pvid"]
            ]
            if len(pvid_vlan) > 0 and (
                interface.mode is None
                or interface.mode.value != self.dcim_choices["interface:mode"]["Access"]
                or interface.untagged_vlan is None
                or interface.untagged_vlan.vid != int(pvid_vlan[0])
            ):
                logging.info(
                    "Resetting access VLAN on interface {interface}".format(interface=interface)
                )
                update = True
                nb_vlan = self.get_or_create_vlan(pvid_vlan[0])
                interface.mode = self.dcim_choices["interface:mode"]["Access"]
                interface.untagged_vlan = nb_vlan.id
        return update, interface

    def update_interface_macs(self, nic, macs):
        nb_macs = list(self.nb_net.mac_addresses.filter(interface_id=nic.id))
        # Clean
        for nb_mac in nb_macs:
            if nb_mac.mac_address not in macs:
                logging.debug("Deleting extra MAC {mac} from {nic}".format(mac=nb_mac, nic=nic))
                nb_mac.delete()
        # Add missing
        for mac in macs:
            if mac not in {nb_mac.mac_address for nb_mac in nb_macs}:
                logging.debug("Adding MAC {mac} to {nic}".format(mac=mac, nic=nic))
                self.nb_net.mac_addresses.create(
                    {
                        "mac_address": mac,
                        "assigned_object_type": "dcim.interface",
                        "assigned_object_id": nic.id,
                    }
                )

    def create_netbox_nic(self, nic, mgmt=False):
        # TODO: add Optic Vendor, PN and Serial
        nic_type = self.get_netbox_type_for_nic(nic)
        logging.info(
            "Creating NIC {name} ({mac}) on {device}".format(
                name=nic["name"], mac=nic["mac"], device=self.device.name
            )
        )

        nb_vlan = None

        params = dict(self.custom_arg)
        params.update(
            {
                "name": nic["name"],
                "type": nic_type,
                "mgmt_only": mgmt,
            }
        )
        if nic["mac"]:
            params["mac_address"] = nic["mac"]

        if nic["mtu"]:
            params["mtu"] = nic["mtu"]

        if nic.get("ethtool") and nic["ethtool"].get("link") == "no":
            params["enabled"] = False

        interface = self.nb_net.interfaces.create(**params)

        if nic["vlan"]:
            nb_vlan = self.get_or_create_vlan(nic["vlan"])
            interface.mode = self.dcim_choices["interface:mode"]["Tagged"]
            interface.tagged_vlans = [nb_vlan.id]
            interface.save()
        elif config.network.lldp and self.lldp.get_switch_vlan(nic["name"]) is not None:
            # if lldp reports a vlan on an interface, tag the interface in access and set the vlan
            # report only the interface which has `pvid=yes` (ie: lldp.eth3.vlan.pvid=yes)
            # if pvid is not present, it'll be processed as a vlan tagged interface
            vlans = self.lldp.get_switch_vlan(nic["name"])
            for vid, vlan_infos in vlans.items():
                nb_vlan = self.get_or_create_vlan(vid)
                if vlan_infos.get("vid"):
                    interface.mode = self.dcim_choices["interface:mode"]["Access"]
                    interface.untagged_vlan = nb_vlan.id
            interface.save()

        # cable the interface
        if config.network.lldp and isinstance(self, ServerNetwork):
            switch_ip = self.lldp.get_switch_ip(interface.name)
            switch_interface = self.lldp.get_switch_port(interface.name)

            if switch_ip and switch_interface:
                nic_update, interface = self.create_or_update_cable(
                    switch_ip, switch_interface, interface
                )
                if nic_update:
                    logging.debug("Saving changes to interface {interface}".format(interface=interface))
                    interface.save()
        return interface

    def create_or_update_netbox_ip_on_interface(self, ip, interface, vrf):
        """
        Two behaviors:
        - Anycast IP
        * If IP exists and is in Anycast, create a new Anycast one
        * If IP exists and isn't assigned, take it
        * If server is decomissioned, then free IP will be taken

        - Normal IP (can be associated only once)
        * If IP doesn't exist, create it
        * If IP exists and isn't assigned, take it
        * If IP exists and interface is wrong, change interface
        """
        netbox_ips = nb.ipam.ip_addresses.filter(
            address=ip,
        )
        if not netbox_ips:
            logging.info("Create new IP {ip} on {interface}".format(ip=ip, interface=interface))
            query_params = {
                "address": ip,
                "status": "active",
                "assigned_object_type": self.assigned_object_type,
                "assigned_object_id": interface.id,
                "vrf": vrf,
                "status": config.network.status,
                "dns_name": get_fqdn(config),
            }

            netbox_ip = nb.ipam.ip_addresses.create(**query_params)
            return netbox_ip

        netbox_ip = list(netbox_ips)[0]
        # If IP exists in anycast
        if netbox_ip.role and netbox_ip.role.label == "Anycast":
            logging.debug("IP {} is Anycast..".format(ip))
            unassigned_anycast_ip = [x for x in netbox_ips if x.interface is None]
            assigned_anycast_ip = [
                x for x in netbox_ips if x.interface and x.interface.id == interface.id
            ]
            # use the first available anycast ip
            if len(unassigned_anycast_ip):
                logging.info("Assigning existing Anycast IP {} to interface".format(ip))
                netbox_ip = unassigned_anycast_ip[0]
                netbox_ip.interface = interface
                netbox_ip.vrf = vrf
                netbox_ip.dns_name = get_fqdn(config)
                netbox_ip.status = config.network.status
                netbox_ip.save()
            # or if everything is assigned to other servers
            elif not len(assigned_anycast_ip):
                logging.info("Creating Anycast IP {} and assigning it to interface".format(ip))
                query_params = {
                    "address": ip,
                    "status": "active",
                    "role": self.ipam_choices["ip-address:role"]["Anycast"],
                    "tenant": self.tenant.id if self.tenant else None,
                    "assigned_object_type": self.assigned_object_type,
                    "assigned_object_id": interface.id,
                    "vrf": vrf,
                    "status": config.network.status,
                    "dns_name": get_fqdn(config),
                }
                netbox_ip = nb.ipam.ip_addresses.create(**query_params)
            return netbox_ip
        else:
            assigned_object = getattr(netbox_ip, "assigned_object", None)
            if not assigned_object:
                logging.info(
                    "Assigning existing IP {ip} to {interface}".format(ip=ip, interface=interface)
                )
            elif assigned_object.id != interface.id:
                old_interface = getattr(netbox_ip, "assigned_object", "n/a")
                logging.info(
                    "Detected interface change for ip {ip}: old interface is "
                    "{old_interface} (id: {old_id}), new interface is {new_interface} "
                    " (id: {new_id})".format(
                        old_interface=old_interface,
                        new_interface=interface,
                        old_id=netbox_ip.id,
                        new_id=interface.id,
                        ip=netbox_ip.address,
                    )
                )
            else:
                return netbox_ip

            netbox_ip.assigned_object_type = self.assigned_object_type
            netbox_ip.assigned_object_id = interface.id
            netbox_ip.vrf = vrf
            netbox_ip.dns_name = get_fqdn(config)
            netbox_ip.status = config.network.status
            netbox_ip.save()

    def _nic_identifier(self, nic):
        if isinstance(nic, dict):
            if config.network.nic_id == "mac":
                if not nic["mac"]:
                    logging.warning(
                        "%s: MAC not available while trying to use it as the NIC identifier",
                        nic["name"],
                    )
                return nic["mac"]
            return nic["name"]
        else:
            if config.network.nic_id == "mac":
                if not nic.mac_address:
                    logging.warning(
                        "%s: MAC not available while trying to use it as the NIC identifier",
                        nic.name,
                    )
                return nic.mac_address
            return nic.name

    def create_or_update_netbox_network_cards(self):
        if config.update_all is None or config.update_network is None:
            return None
        logging.debug("Creating/Updating NIC...")

        # delete unknown interface
        nb_nics = list(self.get_netbox_network_cards())
        local_nics = [self._nic_identifier(x) for x in self.nics]
        for nic in list(nb_nics):
            if self._nic_identifier(nic) not in local_nics:
                logging.info(
                    "Deleting netbox interface {name} because not present locally".format(
                        name=nic.name
                    )
                )
                nb_nics.remove(nic)
                nic.delete()

        # delete IP on netbox that are not known on this server
        if len(nb_nics):

            def batched(it, n):
                while batch := tuple(islice(it, n)):
                    yield batch

            netbox_ips = []
            for ids in batched((x.id for x in nb_nics), 25):
                netbox_ips += list(nb.ipam.ip_addresses.filter(**{self.intf_type: ids}))

            all_local_ips = list(
                chain.from_iterable([x["ip"] for x in self.nics if x["ip"] is not None])
            )
            for netbox_ip in netbox_ips:
                if netbox_ip.address not in all_local_ips:
                    logging.info(
                        "Unassigning IP {ip} from {interface}".format(
                            ip=netbox_ip.address, interface=netbox_ip.assigned_object
                        )
                    )
                    netbox_ip.assigned_object_type = None
                    netbox_ip.assigned_object_id = None
                    netbox_ip.save()

        # create each nic
        interfaces = []
        for nic in self.nics:
            interface = self.get_netbox_network_card(nic)

            if not interface:
                logging.info(
                    "Interface {nic} not found, creating..".format(nic=self._nic_identifier(nic))
                )
                interface = self.create_netbox_nic(nic)
            interfaces.append(interface)

        #restart loop once everything has been create for updates
        for index, nic in enumerate(self.nics):
            interface = interfaces[index]
            nic_update = 0

            ret, interface = self.reset_vlan_on_interface(nic, interface)
            nic_update += ret

            if nic["name"] != interface.name:
                logging.info(
                    "Updating interface {interface} name to: {name}".format(
                        interface=interface, name=nic["name"]
                    )
                )
                interface.name = nic["name"]
                nic_update += 1

            if version.parse(nb.version) >= version.parse("4.2"):
                # Create MAC objects
                if nic["mac"]:
                    self.update_interface_macs(interface, [nic["mac"]])

            vrf = None
            if config.network.vrf and config.network.vrf != str(interface.vrf):
                logging.info(
                    "Updating interface {interface} VRF to: {vrf}".format(
                        interface=interface, vrf=config.network.vrf
                    )
                )
                vrf = self.get_vrf_id(config.network.vrf)
                interface.vrf = vrf
                nic_update += 1

            if nic["mac"] and nic["mac"] != interface.mac_address:
                logging.info(
                    "Updating interface {interface} mac to: {mac}".format(
                        interface=interface, mac=nic["mac"]
                    )
                )
                if version.parse(nb.version) < version.parse("4.2"):
                    interface.mac_address = nic["mac"]
                else:
                    nb_macs = list(self.nb_net.mac_addresses.filter(interface_id=interface.id))
                    interface.primary_mac_address = {"mac_address": nic["mac"], "id": nb_macs[0].id}
                nic_update += 1

            if hasattr(interface, "mtu"):
                if nic["mtu"] != interface.mtu:
                    logging.info(
                        "Interface mtu is wrong, updating to: {mtu}".format(mtu=nic["mtu"])
                    )
                    interface.mtu = nic["mtu"]
                    nic_update += 1

            if hasattr(nic, 'virtual'):
                if nic["virtual"] and nic["parent"] and nic["parent"] != interface.parent:
                    logging.info(
                        "Interface parent is wrong, updating to: {parent}".format(parent=nic["parent"])
                    )
                    for parent_nic in self.nics :
                        if parent_nic["name"] in nic["parent"]:
                            nic_parent = self.get_netbox_network_card(parent_nic)
                            break
                    int_parent = self.get_netbox_network_card(nic_parent)
                    interface.parent = {"name": int_parent.name, "id": int_parent.id}
                    nic_update += 1

            if not isinstance(self, VirtualNetwork) and nic.get("ethtool"):
                if (
                    nic["ethtool"]["duplex"] != "-"
                    and interface.duplex != nic["ethtool"]["duplex"].lower()
                ):
                    interface.duplex = nic["ethtool"]["duplex"].lower()
                    nic_update += 1

                if nic["ethtool"]["speed"] != "-":
                    speed = int(
                        nic["ethtool"]["speed"].replace("Mb/s", "000").replace("Gb/s", "000000")
                    )
                    if speed != interface.speed:
                        interface.speed = speed
                        nic_update += 1

            if hasattr(interface, "type"):
                _type = self.get_netbox_type_for_nic(nic)
                if not interface.type or _type != interface.type.value:
                    logging.info("Interface type is wrong, resetting")
                    interface.type = _type
                    nic_update += 1

            if hasattr(interface, "lag") and interface.lag is not None:
                local_lag_int = next(
                    item for item in self.nics if item["name"] == interface.lag.name
                )
                if nic["name"] not in local_lag_int["bonding_slaves"]:
                    logging.info("Interface has no LAG, resetting")
                    nic_update += 1
                    interface.lag = None

            # cable the interface
            if config.network.lldp and isinstance(self, ServerNetwork):
                switch_ip = self.lldp.get_switch_ip(interface.name)
                switch_interface = self.lldp.get_switch_port(interface.name)
                if switch_ip and switch_interface:
                    ret, interface = self.create_or_update_cable(
                        switch_ip, switch_interface, interface
                    )
                    nic_update += ret

            if nic["ip"]:
                # sync local IPs
                for ip in nic["ip"]:
                    self.create_or_update_netbox_ip_on_interface(ip, interface, vrf)
            if nic_update > 0:
                interface.save()

        self._set_bonding_interfaces()
        self._set_bridged_interfaces()
        logging.debug("Finished updating NIC!")


class ServerNetwork(Network):
    def __init__(self, server, *args, **kwargs):
        super(ServerNetwork, self).__init__(server, args, kwargs)

        if config.network.ipmi:
            self.ipmi = self.get_ipmi()
        if self.ipmi:
            self.nics.append(self.ipmi)

        self.server = server
        self.device = self.server.get_netbox_server()
        self.nb_net = nb.dcim
        self.custom_arg = {"device": getattr(self.device, "id", None)}
        self.custom_arg_id = {"device_id": getattr(self.device, "id", None)}
        self.intf_type = "interface_id"
        self.assigned_object_type = "dcim.interface"

    def get_network_type(self):
        return "server"

    def get_ipmi(self):
        ipmi = IPMI().parse()
        return ipmi

    def connect_interface_to_switch(self, switch_ip, switch_interface, nb_server_interface):
        logging.info(
            "Interface {} is not connected to switch, trying to connect..".format(
                nb_server_interface.name
            )
        )
        nb_mgmt_ip = nb.ipam.ip_addresses.get(
            address=switch_ip,
        )
        if not nb_mgmt_ip:
            logging.error("Switch IP {} cannot be found in Netbox".format(switch_ip))
            return nb_server_interface

        try:
            nb_switch = nb_mgmt_ip.assigned_object.device
            logging.info(
                "Found a switch in Netbox based on LLDP infos: {} (id: {})".format(
                    switch_ip, nb_switch.id
                )
            )
        except (KeyError, AttributeError):
            logging.error(
                "Switch IP {} is found but not associated to a Netbox Switch Device".format(
                    switch_ip
                )
            )
            return nb_server_interface

        switch_interface = self.lldp.get_switch_port(nb_server_interface.name)
        nb_switch_interface = nb.dcim.interfaces.get(
            device_id=nb_switch.id,
            name=switch_interface,
        )
        if nb_switch_interface is None:
            logging.error("Switch interface {} cannot be found".format(switch_interface))
            return nb_server_interface

        logging.info(
            "Found interface {} on switch {}".format(
                switch_interface,
                switch_ip,
            )
        )
        cable = nb.dcim.cables.create(
            a_terminations=[
                {"object_type": "dcim.interface", "object_id": nb_server_interface.id},
            ],
            b_terminations=[
                {"object_type": "dcim.interface", "object_id": nb_switch_interface.id},
            ],
        )
        nb_server_interface.cable = cable
        logging.info(
            "Connected interface {interface} with {switch_interface} of {switch_ip}".format(
                interface=nb_server_interface.name,
                switch_interface=switch_interface,
                switch_ip=switch_ip,
            )
        )
        return nb_server_interface

    def create_or_update_cable(self, switch_ip, switch_interface, nb_server_interface):
        update = False
        if nb_server_interface.cable is None:
            update = True
            nb_server_interface = self.connect_interface_to_switch(
                switch_ip, switch_interface, nb_server_interface
            )
        else:
            nb_sw_int = nb_server_interface.cable.b_terminations[0]
            nb_sw = nb_sw_int.device
            nb_mgmt_int = nb.dcim.interfaces.get(device_id=nb_sw.id, mgmt_only=True)
            if hasattr(nb_mgmt_int, "id"):
                nb_mgmt_ip = nb.ipam.ip_addresses.get(interface_id=nb_mgmt_int.id)
            else: 
                nb_mgmt_ip = None
            if nb_mgmt_ip is None:
                logging.error(
                    "Switch {switch_ip} does not have IP on its management interface".format(
                        switch_ip=switch_ip,
                    )
                )
                return update, nb_server_interface

            # Netbox IP is always IP/Netmask
            nb_mgmt_ip = nb_mgmt_ip.address.split("/")[0]
            if nb_mgmt_ip != switch_ip or nb_sw_int.name != switch_interface:
                logging.info("Netbox cable is not connected to correct ports, fixing..")
                logging.info(
                    "Deleting cable {cable_id} from {interface} to {switch_interface} of "
                    "{switch_ip}".format(
                        cable_id=nb_server_interface.cable.id,
                        interface=nb_server_interface.name,
                        switch_interface=nb_sw_int.name,
                        switch_ip=nb_mgmt_ip,
                    )
                )
                cable = nb.dcim.cables.get(nb_server_interface.cable.id)
                cable.delete()
                update = True
                nb_server_interface = self.connect_interface_to_switch(
                    switch_ip, switch_interface, nb_server_interface
                )
        return update, nb_server_interface


class VirtualNetwork(Network):
    def __init__(self, server, *args, **kwargs):
        super(VirtualNetwork, self).__init__(server, args, kwargs)
        self.server = server
        self.device = self.server.get_netbox_vm()
        self.nb_net = nb.virtualization
        self.custom_arg = {"virtual_machine": getattr(self.device, "id", None)}
        self.custom_arg_id = {"virtual_machine_id": getattr(self.device, "id", None)}
        self.intf_type = "vminterface_id"
        self.assigned_object_type = "virtualization.vminterface"

        dcim_c = nb.virtualization.interfaces.choices()
        for _choice_type in dcim_c:
            key = "interface:{}".format(_choice_type)
            self.dcim_choices[key] = {}
            for choice in dcim_c[_choice_type]:
                self.dcim_choices[key][choice["display_name"]] = choice["value"]

    def get_network_type(self):
        return "virtual"
