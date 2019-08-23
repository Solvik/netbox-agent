from itertools import chain
import logging
import os
import re

from netaddr import IPAddress, IPNetwork
import netifaces

from netbox_agent.config import netbox_instance as nb
from netbox_agent.config import NETWORK_IGNORE_INTERFACES, NETWORK_IGNORE_IPS, NETWORK_LLDP
from netbox_agent.ethtool import Ethtool
from netbox_agent.ipmi import IPMI
from netbox_agent.lldp import LLDP

IFACE_TYPE_100ME_FIXED = 800
IFACE_TYPE_1GE_FIXED = 1000
IFACE_TYPE_1GE_GBIC = 1050
IFACE_TYPE_1GE_SFP = 1100
IFACE_TYPE_2GE_FIXED = 1120
IFACE_TYPE_5GE_FIXED = 1130
IFACE_TYPE_10GE_FIXED = 1150
IFACE_TYPE_10GE_CX4 = 1170
IFACE_TYPE_10GE_SFP_PLUS = 1200
IFACE_TYPE_10GE_XFP = 1300
IFACE_TYPE_10GE_XENPAK = 1310
IFACE_TYPE_10GE_X2 = 1320
IFACE_TYPE_25GE_SFP28 = 1350
IFACE_TYPE_40GE_QSFP_PLUS = 1400
IFACE_TYPE_50GE_QSFP28 = 1420
IFACE_TYPE_100GE_CFP = 1500
IFACE_TYPE_100GE_CFP2 = 1510
IFACE_TYPE_100GE_CFP4 = 1520
IFACE_TYPE_100GE_CPAK = 1550
IFACE_TYPE_100GE_QSFP28 = 1600
IFACE_TYPE_200GE_CFP2 = 1650
IFACE_TYPE_200GE_QSFP56 = 1700
IFACE_TYPE_400GE_QSFP_DD = 1750
IFACE_TYPE_OTHER = 32767
IFACE_TYPE_LAG = 200


class Network():
    def __init__(self, server, *args, **kwargs):
        self.nics = []

        self.server = server
        self.device = self.server.get_netbox_server()
        self.lldp = LLDP()
        self.scan()

    def scan(self):
        for interface in os.listdir('/sys/class/net/'):
            # ignore if it's not a link (ie: bonding_masters etc)
            if not os.path.islink('/sys/class/net/{}'.format(interface)):
                continue

            if NETWORK_IGNORE_INTERFACES and \
               re.match(NETWORK_IGNORE_INTERFACES, interface):
                logging.debug('Ignore interface {interface}'.format(interface=interface))
                continue

            ip_addr = netifaces.ifaddresses(interface).get(netifaces.AF_INET)
            if NETWORK_IGNORE_IPS and ip_addr:
                for i, ip in enumerate(ip_addr):
                    if re.match(NETWORK_IGNORE_IPS, ip['addr']):
                        ip_addr.pop(i)

            mac = open('/sys/class/net/{}/address'.format(interface), 'r').read().strip()
            vlan = None
            if len(interface.split('.')) > 1:
                vlan = int(interface.split('.')[1])
            bonding = False
            bonding_slaves = []
            if os.path.isdir('/sys/class/net/{}/bonding'.format(interface)):
                bonding = True
                bonding_slaves = open(
                    '/sys/class/net/{}/bonding/slaves'.format(interface)
                ).read().split()
            nic = {
                'name': interface,
                'mac': mac if mac != '00:00:00:00:00:00' else None,
                'ip': [
                    '{}/{}'.format(
                        x['addr'],
                        IPAddress(x['netmask']).netmask_bits()
                    ) for x in ip_addr
                    ] if ip_addr else None,  # FIXME: handle IPv6 addresses
                'ethtool': Ethtool(interface).parse(),
                'vlan': vlan,
                'bonding': bonding,
                'bonding_slaves': bonding_slaves,
            }
            self.nics.append(nic)

    def _set_bonding_interfaces(self):
        bonding_nics = (x for x in self.nics if x['bonding'])
        for nic in bonding_nics:
            bond_int = self.get_netbox_network_card(nic)
            logging.debug('Setting slave interface for {name}'.format(
                name=bond_int.name
            ))
            for slave_int in (
                    self.get_netbox_network_card(slave_nic)
                    for slave_nic in self.nics
                    if slave_nic['name'] in nic['bonding_slaves']):
                if slave_int.lag is None or slave_int.lag.id != bond_int.id:
                    logging.debug('Settting interface {name} as slave of {master}'.format(
                        name=slave_int.name, master=bond_int.name
                    ))
                    slave_int.lag = bond_int
                    slave_int.save()
        else:
            return False
        return True

    def get_network_cards(self):
        return self.nics

    def get_netbox_network_card(self, nic):
        if nic['mac'] is None:
            interface = nb.dcim.interfaces.get(
                device_id=self.device.id,
                name=nic['name'],
            )
        else:
            interface = nb.dcim.interfaces.get(
                device_id=self.device.id,
                mac_address=nic['mac'],
                name=nic['name'],
            )
        return interface

    def get_netbox_network_cards(self):
        return nb.dcim.interfaces.filter(
            device_id=self.device.id,
            mgmt_only=False,
        )

    def get_netbox_type_for_nic(self, nic):
        if nic.get('bonding'):
            return IFACE_TYPE_LAG
        if nic.get('ethtool') is None:
            return IFACE_TYPE_OTHER
        if nic['ethtool']['speed'] == '10000Mb/s':
            if nic['ethtool']['port'] == 'FIBRE':
                return IFACE_TYPE_10GE_SFP_PLUS
            return IFACE_TYPE_10GE_FIXED
        elif nic['ethtool']['speed'] == '1000Mb/s':
            if nic['ethtool']['port'] == 'FIBRE':
                return IFACE_TYPE_1GE_SFP
            return IFACE_TYPE_1GE_FIXED
        return IFACE_TYPE_OTHER

    def get_ipmi(self):
        ipmi = IPMI().parse()
        return ipmi

    def get_netbox_ipmi(self):
        ipmi = self.get_ipmi()
        mac = ipmi['MAC Address']
        return nb.dcim.interfaces.get(
            mac=mac
        )

    def get_or_create_vlan(self, vlan_id):
        # FIXME: we may need to specify the datacenter
        # since users may have same vlan id in multiple dc
        vlan = nb.ipam.vlans.get(
            vid=vlan_id,
        )
        if vlan is None:
            vlan = nb.ipam.vlans.create(
                name='VLAN {}'.format(vlan_id),
                vid=vlan_id,
            )
        return vlan

    def reset_vlan_on_interface(self, vlan_id, interface):
        update = False
        if vlan_id is None and \
           (interface.mode is not None or len(interface.tagged_vlans) > 0):
            logging.info('Interface {interface} is not tagged, reseting mode'.format(
                interface=interface))
            update = True
            interface.mode = None
            interface.tagged_vlans = []
        elif vlan_id and (
                interface.mode is None or
                len(interface.tagged_vlans) != 1 or
                interface.tagged_vlans[0].vid != vlan_id):
            logging.info('Resetting VLAN on interface {interface}'.format(
                interface=interface))
            update = True
            nb_vlan = self.get_or_create_vlan(vlan_id)
            interface.mode = 200
            interface.tagged_vlans = [nb_vlan] if nb_vlan else []
        return update, interface

    def create_or_update_ipmi(self):
        ipmi = self.get_ipmi()
        mac = ipmi['MAC Address']
        ip = ipmi['IP Address']
        netmask = ipmi['Subnet Mask']
        vlan = int(ipmi['802.1q VLAN ID']) if ipmi['802.1q VLAN ID'] != 'Disabled' else None
        address = str(IPNetwork('{}/{}'.format(ip, netmask)))

        interface = nb.dcim.interfaces.get(
            device_id=self.device.id,
            mgmt_only=True,
            )
        nic = {
            'name': 'IPMI',
            'mac': mac,
            'vlan': vlan,
            'ip': [address],
        }
        if interface is None:
            interface = self.create_netbox_nic(nic, mgmt=True)
            self.create_or_update_netbox_ip_on_interface(address, interface)
        else:
            # let the user chose the name of mgmt ?
            # guess it with manufacturer (IDRAC, ILO, ...) ?
            update = False
            self.create_or_update_netbox_ip_on_interface(address, interface)
            update, interface = self.reset_vlan_on_interface(nic['vlan'], interface)
            if mac.upper() != interface.mac_address:
                logging.info('IPMI mac changed from {old_mac} to {new_mac}'.format(
                    old_mac=interface.mac_address, new_mac=mac.upper()))
                interface.mac_address = mac
                update = True
            if update:
                interface.save()
        return interface

    def create_netbox_nic(self, nic, mgmt=False):
        # TODO: add Optic Vendor, PN and Serial
        type = self.get_netbox_type_for_nic(nic)
        logging.info('Creating NIC {name} ({mac}) on {device}'.format(
            name=nic['name'], mac=nic['mac'], device=self.device.name))

        nb_vlan = None
        if nic['vlan']:
            nb_vlan = self.get_or_create_vlan(nic['vlan'])
        return nb.dcim.interfaces.create(
            device=self.device.id,
            name=nic['name'],
            mac_address=nic['mac'],
            type=type,
            mode=200 if nic['vlan'] else None,
            tagged_vlans=[nb_vlan.id] if nb_vlan is not None else [],
            mgmt_only=mgmt,
        )

    def create_or_update_netbox_ip_on_interface(self, ip, interface):
        netbox_ip = nb.ipam.ip_addresses.get(
            address=ip,
        )
        if netbox_ip:
            if netbox_ip.interface is None:
                logging.info('Assigning existing IP {ip} to {interface}'.format(
                    ip=ip, interface=interface))
            elif netbox_ip.interface.id != interface.id:
                logging.info(
                    'Detected interface change for ip {ip}: old interface is '
                    '{old_interface} (id: {old_id}), new interface is {new_interface} '
                    ' (id: {new_id})'
                    .format(
                        old_interface=netbox_ip.interface, new_interface=interface,
                        old_id=netbox_ip.id, new_id=interface.id, ip=netbox_ip.address
                    ))
            else:
                return netbox_ip
            netbox_ip.interface = interface
            netbox_ip.save()
        else:
            logging.info('Create new IP {ip} on {interface}'.format(
                ip=ip, interface=interface))
            netbox_ip = nb.ipam.ip_addresses.create(
                address=ip,
                interface=interface.id,
                status=1,
            )
        return netbox_ip

    def create_netbox_network_cards(self):
        logging.debug('Creating NIC...')
        for nic in self.nics:
            interface = self.get_netbox_network_card(nic)
            # if network doesn't exist we create it
            if not interface:
                new_interface = self.create_netbox_nic(nic)
                if nic['ip']:
                    # for each ip, we try to find it
                    # assign the device's interface to it
                    # or simply create it
                    for ip in nic['ip']:
                        self.create_or_update_netbox_ip_on_interface(ip, new_interface)
        self._set_bonding_interfaces()
        self.create_or_update_ipmi()
        logging.debug('Finished creating NIC!')

    def connect_interface_to_switch(self, switch_ip, switch_interface, nb_server_interface):
        logging.info('Interface {} is not connected to switch, trying to connect..'.format(
            nb_server_interface.name
        ))
        nb_mgmt_ip = nb.ipam.ip_addresses.get(
            address=switch_ip,
        )
        if not nb_mgmt_ip:
            logging.error('Switch IP {} cannot be found in Netbox'.format(switch_ip))
            return nb_server_interface

        try:
            nb_switch = nb_mgmt_ip.interface.device
            logging.info('Found a switch in Netbox based on LLDP infos: {} (id: {})'.format(
                switch_ip,
                nb_switch.id
            ))
        except KeyError:
            logging.error(
                'Switch IP {} is found but not associated to a Netbox Switch Device'.format(
                    switch_ip
                )
            )
            return nb_server_interface

        switch_interface = self.lldp.get_switch_port(nb_server_interface.name)
        nb_switch_interface = nb.dcim.interfaces.get(
            device=nb_switch,
            name=switch_interface,
        )
        if nb_switch_interface is None:
            logging.error('Switch interface {} cannot be found'.format(switch_interface))
            return nb_server_interface

        logging.info('Found interface {} on switch {}'.format(
            switch_interface,
            switch_ip,
        ))
        cable = nb.dcim.cables.create(
            termination_a_id=nb_server_interface.id,
            termination_a_type="dcim.interface",
            termination_b_id=nb_switch_interface.id,
            termination_b_type="dcim.interface",
        )
        nb_server_interface.cable = cable
        logging.info(
            'Connected interface {interface} with {switch_interface} of {switch_ip}'.format(
                interface=nb_server_interface.name,
                switch_interface=switch_interface,
                switch_ip=switch_ip,
            )
        )
        return nb_server_interface

    def create_or_update_cable(self, switch_ip, switch_interface, nb_server_interface):
        if nb_server_interface.cable is None:
            update = True
            nb_server_interface = self.connect_interface_to_switch(
                switch_ip, switch_interface, nb_server_interface
            )
        else:
            update = False
            nb_sw_int = nb_server_interface.cable.termination_b
            nb_sw = nb_sw_int.device
            nb_mgmt_int = nb.dcim.interfaces.get(
                device_id=nb_sw.id,
                mgmt_only=True
            )
            nb_mgmt_ip = nb.ipam.ip_addresses.get(
                interface_id=nb_mgmt_int.id
            )
            if nb_mgmt_ip is None:
                pass

            # Netbox IP is always IP/Netmask
            nb_mgmt_ip = nb_mgmt_ip.address.split('/')[0]
            if nb_mgmt_ip != switch_ip or \
               nb_sw_int.name != switch_interface:
                logging.info('Netbox cable is not connected to correct ports, fixing..')
                logging.info(
                    'Deleting cable {cable_id} from {interface} to {switch_interface} of '
                    '{switch_ip}'.format(
                        cable_id=nb_server_interface.cable.id,
                        interface=nb_server_interface.name,
                        switch_interface=nb_sw_int.name,
                        switch_ip=nb_mgmt_ip,
                    )
                )
                cable = nb.dcim.cables.get(
                    nb_server_interface.cable.id
                )
                print(cable)
                cable.delete()
                update = True
                nb_server_interface = self.connect_interface_to_switch(
                    switch_ip, switch_interface, nb_server_interface
                )
        return update, nb_server_interface

    def update_netbox_network_cards(self):
        logging.debug('Updating NIC...')

        # delete unknown interface
        nb_nics = self.get_netbox_network_cards()
        local_nics = [x['name'] for x in self.nics]
        for nic in nb_nics:
            if nic.name not in local_nics:
                logging.info('Deleting netbox interface {name} because not present locally'.format(
                    name=nic.name
                ))
                nic.delete()

        # delete IP on netbox that are not known on this server
        netbox_ips = nb.ipam.ip_addresses.filter(
            device_id=self.device.id,
            interface_id=[x.id for x in nb_nics],
        )
        all_local_ips = list(chain.from_iterable([
            x['ip'] for x in self.nics if x['ip'] is not None
        ]))
        for netbox_ip in netbox_ips:
            if netbox_ip.address not in all_local_ips:
                logging.info('Unassigning IP {ip} from {interface}'.format(
                    ip=netbox_ip.address, interface=netbox_ip.interface))
                netbox_ip.interface = None
                netbox_ip.save()

        # update each nic
        for nic in self.nics:
            interface = self.get_netbox_network_card(nic)
            if not interface:
                logging.info('Interface {mac_address} not found, creating..'.format(
                    mac_address=nic['mac'])
                )
                interface = self.create_netbox_nic(nic)

            nic_update = False
            if nic['name'] != interface.name:
                nic_update = True
                logging.info('Updating interface {interface} name to: {name}'.format(
                    interface=interface, name=nic['name']))
                interface.name = nic['name']

            nic_update, interface = self.reset_vlan_on_interface(nic['vlan'], interface)

            type = self.get_netbox_type_for_nic(nic)
            if not interface.type or \
               type != interface.type.value:
                logging.info('Interface type is wrong, resetting')
                nic_update = True
                interface.type = type

            if interface.lag is not None:
                local_lag_int = next(
                    item for item in self.nics if item['name'] == interface.lag.name
                )
                if nic['name'] not in local_lag_int['bonding_slaves']:
                    logging.info('Interface has no LAG, resetting')
                    nic_update = True
                    interface.lag = None

            # cable the interface
            if NETWORK_LLDP:
                switch_ip = self.lldp.get_switch_ip(interface.name)
                switch_interface = self.lldp.get_switch_port(interface.name)
                nic_update, interface = self.create_or_update_cable(
                    switch_ip, switch_interface, interface
                )

            if nic['ip']:
                # sync local IPs
                for ip in nic['ip']:
                    self.create_or_update_netbox_ip_on_interface(ip, interface)
            if nic_update:
                interface.save()

        self._set_bonding_interfaces()
        self.create_or_update_ipmi()
        logging.debug('Finished updating NIC!')
