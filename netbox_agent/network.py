import os
import re
import subprocess

from netaddr import IPAddress
import netifaces

from netbox_agent.config import netbox_instance as nb
from netbox_agent.ethtool import parse_ethtool_output

# Regex to match base interface name
# Doesn't match vlan interfaces and other loopback etc
INTERFACE_REGEX = re.compile('^(eth[0-9]+|ens[0-9]+|enp[0-9]+s[0-9]f[0-9])$')

# FIXME: finish mapping tabble
ETHTOOL_TO_NETBOX_TYPE = {
    1200: 'SFP+ (10GE)',
    1150: '10g baseT',
    1000: '1G cuivre',
    1400: '40G',
    }


class Network():
    def __init__(self, server, *args, **kwargs):
        self.nics = []

        self.server = server
        self.scan()

    def _ethtool_for_interface(self, interface):
        output = subprocess.getoutput('ethtool {}'.format(interface))
        return parse_ethtool_output(output)

    def scan(self):
        for interface in os.listdir('/sys/class/net/'):
            if re.match(INTERFACE_REGEX, interface):
                ip_addr = netifaces.ifaddresses(interface).get(netifaces.AF_INET)
                nic = {
                    'name': interface,
                    'mac': open('/sys/class/net/{}/address'.format(interface), 'r').read().strip(),
                    'ip': [
                        '{}/{}'.format(
                            x['addr'],
                            IPAddress(x['netmask']).netmask_bits()
                        ) for x in ip_addr
                        ] if ip_addr else None,  # FIXME: handle IPv6 addresses
                    'ethtool': self._ethtool_for_interface(interface)
                }
                self.nics.append(nic)

    def get_network_cards(self):
        return self.nics

    def update_netbox_network_cards(self):
        device = self.server.get_netbox_server()
        for nic in self.nics:
            interface = nb.dcim.interfaces.get(
                device=device,
                mac_address=nic['mac'],
                )
            # if network doesn't exist we create it
            if not interface:
                new_interface = nb.dcim.interfaces.create(
                    device=device.id,
                    name=nic['name'],
                    mac_address=nic['mac'],
                    )
                if nic['ip']:
                    # for each ip, we try to find it
                    # assign the device's interface to it
                    # or simply create it
                    for ip in nic['ip']:
                        netbox_ip = nb.ipam.ip_addresses.get(
                            address=ip,
                        )
                        if netbox_ip:
                            netbox_ip.interface = new_interface
                            netbox_ip.save()
                        else:
                            netbox_ip = nb.ipam.ip_addresses.create(
                                address=ip,
                                interface=new_interface.id,
                                status=1,
                            )
            # or we check if it needs update
            else:
                # FIXME: implement update
                # update name or ip
                # see https://github.com/Solvik/netbox_agent/issues/9
                pass
