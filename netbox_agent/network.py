from itertools import chain
import logging
import os
import re

from netaddr import IPAddress
import netifaces

from netbox_agent.config import netbox_instance as nb
from netbox_agent.config import NETWORK_IGNORE_INTERFACES, NETWORK_IGNORE_IPS
from netbox_agent.ethtool import Ethtool

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
            else:
                ip_addr = netifaces.ifaddresses(interface).get(netifaces.AF_INET)
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
                        ) for x in ip_addr if not re.match(NETWORK_IGNORE_IPS, x['addr'])
                        ] if ip_addr else None,  # FIXME: handle IPv6 addresses
                    'ethtool': Ethtool(interface).parse(),
                    'vlan': vlan,
                    'bonding': bonding,
                    'bonding_slaves': bonding_slaves,
                }
                self.nics.append(nic)

    def _set_bonding_interfaces(self):
        logging.debug('Setting bonding interfaces..')
        for nic in [x for x in self.nics if x['bonding']]:
            bond_int = self.get_netbox_network_card(nic)
            logging.debug('Setting slave interface for {name}'.format(
                name=bond_int.name
            ))
            for slave in nic['bonding_slaves']:
                slave_nic = next(item for item in self.nics if item['name'] == slave)
                slave_int  = self.get_netbox_network_card(slave_nic)
                logging.debug('Settting interface {name} as slave of {master}'.format(
                    name=slave_int.name, master=bond_int.name
                ))
                slave_int.lag = bond_int
                slave_int.save()

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
        )

    def get_netbox_type_for_nic(self, nic):
        if nic['bonding']:
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

    def create_netbox_nic(self, nic):
        # TODO: add Optic Vendor, PN and Serial
        type = self.get_netbox_type_for_nic(nic)
        logging.info('Creating NIC {name} ({mac}) on {device}'.format(
            name=nic['name'], mac=nic['mac'], device=self.device.name))
        return nb.dcim.interfaces.create(
            device=self.device.id,
            name=nic['name'],
            mac_address=nic['mac'],
            type=type,
            mode=200 if nic['vlan'] else None,
        )

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
                        netbox_ip = nb.ipam.ip_addresses.get(
                            address=ip,
                        )
                        if netbox_ip:
                            logging.info('Assigning existing IP {ip} to {interface}'.format(
                                ip=ip, interface=new_interface))
                            netbox_ip.interface = new_interface
                            netbox_ip.save()
                        else:
                            logging.info('Create new IP {ip} on {interface}'.format(
                                ip=ip, interface=new_interface))
                            netbox_ip = nb.ipam.ip_addresses.create(
                                address=ip,
                                interface=new_interface.id,
                                status=1,
                            )
        self._set_bonding_interfaces()
        logging.debug('Finished creating NIC!')

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
            device_id=self.device.id
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

            if nic['ip']:
                # sync local IPs
                for ip in nic['ip']:
                    netbox_ip = nb.ipam.ip_addresses.get(
                        address=ip,
                    )
                    if not netbox_ip:
                        # create netbox_ip on device
                        netbox_ip = nb.ipam.ip_addresses.create(
                            address=ip,
                            interface=interface.id,
                            status=1,
                        )
                        logging.info('Created new IP {ip} on {interface}'.format(
                            ip=ip, interface=interface))
                    else:
                        if netbox_ip.interface.id != interface.id:
                            logging.info(
                                'Detected interface change: old interface is {old_interface} '
                                '(id: {old_id}), new interface is {new_interface} (id: {new_id})'
                                .format(
                                    old_interface=netbox_ip.interface, new_interface=interface,
                                    old_id=netbox_ip.id, new_id=interface.id
                                ))
                            netbox_ip.interface = interface
                            netbox_ip.save()
            if nic_update:
                interface.save()

        self._set_bonding_interfaces()
        logging.debug('Finished updating NIC!')
