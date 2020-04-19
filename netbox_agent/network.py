import logging
import os
import re
from itertools import chain

import netifaces
from netaddr import IPAddress

from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.ethtool import Ethtool
from netbox_agent.ipmi import IPMI
from netbox_agent.lldp import LLDP


class Network(object):
    def __init__(self, server, *args, **kwargs):
        self.nics = []

        self.lldp = LLDP() if config.network.lldp else None
        self.nics = self.scan()
        self.ipmi = None
        self.dcim_choices = {}
        dcim_c = nb.dcim.choices()

        for choice in dcim_c:
            self.dcim_choices[choice] = {}
            for c in dcim_c[choice]:
                self.dcim_choices[choice][c['label']] = c['value']

        self.ipam_choices = {}
        ipam_c = nb.ipam.choices()

        for choice in ipam_c:
            self.ipam_choices[choice] = {}
            for c in ipam_c[choice]:
                self.ipam_choices[choice][c['label']] = c['value']

    def get_network_type():
        return NotImplementedError

    def scan(self):
        nics = []
        for interface in os.listdir('/sys/class/net/'):
            # ignore if it's not a link (ie: bonding_masters etc)
            if not os.path.islink('/sys/class/net/{}'.format(interface)):
                continue

            if config.network.ignore_interfaces and \
               re.match(config.network.ignore_interfaces, interface):
                logging.debug('Ignore interface {interface}'.format(interface=interface))
                continue

            ip_addr = netifaces.ifaddresses(interface).get(netifaces.AF_INET, [])
            ip6_addr = netifaces.ifaddresses(interface).get(netifaces.AF_INET6, [])

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
                addr["addr"] = addr["addr"].replace('%{}'.format(interface), '')
                addr["netmask"] = addr["netmask"].split('/')[0]
                ip_addr.append(addr)

            if config.network.ignore_ips and ip_addr:
                for i, ip in enumerate(ip_addr):
                    if re.match(config.network.ignore_ips, ip['addr']):
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
            nics.append(nic)
        return nics

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
            interface = self.nb_net.interfaces.get(
                name=nic['name'],
                **self.custom_arg_id,
            )
        else:
            interface = self.nb_net.interfaces.get(
                mac_address=nic['mac'],
                name=nic['name'],
                **self.custom_arg_id,
            )
        return interface

    def get_netbox_network_cards(self):
        return self.nb_net.interfaces.filter(
            **self.custom_arg_id,
        )

    def get_netbox_type_for_nic(self, nic):
        if self.get_network_type() == 'virtual':
            return self.dcim_choices['interface:type']['Virtual']

        if nic.get('bonding'):
            return self.dcim_choices['interface:type']['Link Aggregation Group (LAG)']

        if nic.get('bonding'):
            return self.dcim_choices['interface:type']['Link Aggregation Group (LAG)']
        if nic.get('ethtool') is None:
            return self.dcim_choices['interface:type']['Other']

        if nic['ethtool']['speed'] == '10000Mb/s':
            if nic['ethtool']['port'] == 'FIBRE':
                return self.dcim_choices['interface:type']['SFP+ (10GE)']
            return self.dcim_choices['interface:type']['10GBASE-T (10GE)']

        elif nic['ethtool']['speed'] == '1000Mb/s':
            if nic['ethtool']['port'] == 'FIBRE':
                return self.dcim_choices['interface:type']['SFP (1GE)']
            return self.dcim_choices['interface:type']['1000BASE-T (1GE)']
        return self.dcim_choices['interface:type']['Other']

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

    def reset_vlan_on_interface(self, nic, interface):
        update = False
        vlan_id = nic['vlan']
        lldp_vlan = self.lldp.get_switch_vlan(nic['name']) if config.network.lldp else None

        # if local interface isn't a interface vlan or lldp doesn't report a vlan-id
        if vlan_id is None and lldp_vlan is None and \
           (interface.mode is not None or len(interface.tagged_vlans) > 0):
            logging.info('Interface {interface} is not tagged, reseting mode'.format(
                interface=interface))
            update = True
            interface.mode = None
            interface.tagged_vlans = []
            interface.untagged_vlan = None
        # if it's a vlan interface
        elif vlan_id and (
                interface.mode is None or
                type(interface.mode) is not int and (
                    interface.mode.value == self.dcim_choices['interface:mode']['Access'] or
                    len(interface.tagged_vlans) != 1 or
                    interface.tagged_vlans[0].vid != vlan_id)):
            logging.info('Resetting tagged VLAN(s) on interface {interface}'.format(
                interface=interface))
            update = True
            nb_vlan = self.get_or_create_vlan(vlan_id)
            interface.mode = self.dcim_choices['interface:mode']['Tagged']
            interface.tagged_vlans = [nb_vlan] if nb_vlan else []
            interface.untagged_vlan = None
        # if lldp reports a vlan-id with pvid
        elif lldp_vlan:
            pvid_vlan = [key for (key, value) in lldp_vlan.items() if value['pvid']]
            if len(pvid_vlan) > 0 and (
                    interface.mode is None or
                    interface.mode.value != self.dcim_choices['interface:mode']['Access'] or
                    interface.untagged_vlan is None or
                    interface.untagged_vlan.vid != int(pvid_vlan[0])):
                logging.info('Resetting access VLAN on interface {interface}'.format(
                    interface=interface))
                update = True
                nb_vlan = self.get_or_create_vlan(pvid_vlan[0])
                interface.mode = self.dcim_choices['interface:mode']['Access']
                interface.untagged_vlan = nb_vlan.id
        return update, interface

    def create_netbox_nic(self, nic, mgmt=False):
        # TODO: add Optic Vendor, PN and Serial
        type = self.get_netbox_type_for_nic(nic)
        logging.info('Creating NIC {name} ({mac}) on {device}'.format(
            name=nic['name'], mac=nic['mac'], device=self.device.name))

        nb_vlan = None
        interface = self.nb_net.interfaces.create(
            name=nic['name'],
            mac_address=nic['mac'],
            type=type,
            mgmt_only=mgmt,
            **self.custom_arg,
        )

        if nic['vlan']:
            nb_vlan = self.get_or_create_vlan(nic['vlan'])
            interface.mode = 200
            interface.tagged_vlans = [nb_vlan.id]
            interface.save()
        elif config.network.lldp and self.lldp.get_switch_vlan(nic['name']) is not None:
            # if lldp reports a vlan on an interface, tag the interface in access and set the vlan
            # report only the interface which has `pvid=yes` (ie: lldp.eth3.vlan.pvid=yes)
            # if pvid is not present, it'll be processed as a vlan tagged interface
            vlans = self.lldp.get_switch_vlan(nic['name'])
            for vid, vlan_infos in vlans.items():
                nb_vlan = self.get_or_create_vlan(vid)
                if vlan_infos.get('vid'):
                    interface.mode = self.dcim_choices['interface:mode']['Access']
                    interface.untagged_vlan = nb_vlan.id
            interface.save()

        # cable the interface
        if config.network.lldp:
            switch_ip = self.lldp.get_switch_ip(interface.name)
            switch_interface = self.lldp.get_switch_port(interface.name)

            if switch_ip and switch_interface:
                nic_update, interface = self.create_or_update_cable(
                    switch_ip, switch_interface, interface
                )
                if nic_update:
                    interface.save()
        return interface

    def create_or_update_netbox_ip_on_interface(self, ip, interface):
        '''
        Two behaviors:
        - Anycast IP
        * If IP exists and is in Anycast, create a new Anycast one
        * If IP exists and isn't assigned, take it
        * If server is decomissioned, then free IP will be taken

        - Normal IP (can be associated only once)
        * If IP doesn't exist, create it
        * If IP exists and isn't assigned, take it
        * If IP exists and interface is wrong, change interface
        '''
        netbox_ips = nb.ipam.ip_addresses.filter(
            address=ip,
        )
        if not len(netbox_ips):
            logging.info('Create new IP {ip} on {interface}'.format(
                ip=ip, interface=interface))
            netbox_ip = nb.ipam.ip_addresses.create(
                address=ip,
                interface=interface.id,
                status=1,
            )
        else:
            netbox_ip = netbox_ips[0]
            # If IP exists in anycast
            if netbox_ip.role and netbox_ip.role.label == 'Anycast':
                logging.debug('IP {} is Anycast..'.format(ip))
                unassigned_anycast_ip = [x for x in netbox_ips if x.interface is None]
                assigned_anycast_ip = [x for x in netbox_ips if
                                       x.interface and x.interface.id == interface.id]
                # use the first available anycast ip
                if len(unassigned_anycast_ip):
                    logging.info('Assigning existing Anycast IP {} to interface'.format(ip))
                    netbox_ip = unassigned_anycast_ip[0]
                    netbox_ip.interface = interface
                    netbox_ip.save()
                # or if everything is assigned to other servers
                elif not len(assigned_anycast_ip):
                    logging.info('Creating Anycast IP {} and assigning it to interface'.format(ip))
                    netbox_ip = nb.ipam.ip_addresses.create(
                        address=ip,
                        interface=interface.id,
                        status=1,
                        role=self.ipam_choices['ip-address:role']['Anycast'],
                    )
                return netbox_ip
            else:
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
        return netbox_ip

    def create_or_update_netbox_network_cards(self):
        if config.update_all is None or config.update_network is None:
            return None
        logging.debug('Creating/Updating NIC...')

        # delete unknown interface
        nb_nics = self.get_netbox_network_cards()
        local_nics = [x['name'] for x in self.nics]
        for nic in nb_nics[:]:
            if nic.name not in local_nics:
                logging.info('Deleting netbox interface {name} because not present locally'.format(
                    name=nic.name
                ))
                nb_nics.remove(nic)
                nic.delete()

        # delete IP on netbox that are not known on this server
        if len(nb_nics):
            netbox_ips = nb.ipam.ip_addresses.filter(
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

            nic_update = 0
            if nic['name'] != interface.name:
                logging.info('Updating interface {interface} name to: {name}'.format(
                    interface=interface, name=nic['name']))
                interface.name = nic['name']
                nic_update += 1

            ret, interface = self.reset_vlan_on_interface(nic, interface)
            nic_update += ret

            _type = self.get_netbox_type_for_nic(nic)
            if not interface.type or \
               _type != interface.type.value:
                logging.info('Interface type is wrong, resetting')
                interface.type = _type
                nic_update += 1

            if hasattr(interface, 'lag') and interface.lag is not None:
                local_lag_int = next(
                    item for item in self.nics if item['name'] == interface.lag.name
                )
                if nic['name'] not in local_lag_int['bonding_slaves']:
                    logging.info('Interface has no LAG, resetting')
                    nic_update += 1
                    interface.lag = None

            # cable the interface
            if config.network.lldp:
                switch_ip = self.lldp.get_switch_ip(interface.name)
                switch_interface = self.lldp.get_switch_port(interface.name)
                if switch_ip and switch_interface:
                    ret, interface = self.create_or_update_cable(
                        switch_ip, switch_interface, interface
                    )
                    nic_update += ret

            if nic['ip']:
                # sync local IPs
                for ip in nic['ip']:
                    self.create_or_update_netbox_ip_on_interface(ip, interface)
            if nic_update > 0:
                interface.save()

        self._set_bonding_interfaces()
        logging.debug('Finished updating NIC!')


class ServerNetwork(Network):
    def __init__(self, server, *args, **kwargs):
        super(ServerNetwork, self).__init__(server, args, kwargs)
        self.ipmi = self.get_ipmi()
        if self.ipmi:
            self.nics.append(self.ipmi)
        self.server = server
        self.device = self.server.get_netbox_server()
        self.nb_net = nb.dcim
        self.custom_arg = {'device': self.device.id}
        self.custom_arg_id = {'device_id': self.device.id}

    def get_network_type(self):
        return 'server'

    def get_ipmi(self):
        ipmi = IPMI().parse()
        return ipmi

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
        update = False
        if nb_server_interface.cable is None:
            update = True
            nb_server_interface = self.connect_interface_to_switch(
                switch_ip, switch_interface, nb_server_interface
            )
        else:
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
                logging.error(
                    'Switch {switch_ip} does not have IP on its management interface'.format(
                        switch_ip=switch_ip,
                    )
                )
                return update, nb_server_interface

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
        self.custom_arg = {'virtual_machine': self.device.id}
        self.custom_arg_id = {'virtual_machine_id': self.device.id}

        dcim_c = nb.virtualization.choices()

        for choice in dcim_c:
            self.dcim_choices[choice] = {}
            for c in dcim_c[choice]:
                self.dcim_choices[choice][c['label']] = c['value']

    def get_network_type(self):
        return 'virtual'
