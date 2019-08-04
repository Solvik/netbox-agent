import os
import re
import socket
import subprocess

import netifaces

from netbox_agent.ethtool import parse_ethtool_output
from netbox_agent.config import netbox_instance as nb

# Regex to match base interface name
# Doesn't match vlan interfaces and other loopback etc
INTERFACE_REGEX = re.compile('^(eth[0-9]+|ens[0-9]+|enp[0-9]+s[0-9]f[0-9])$')

class Network():
    def __init__(self, *args, **kwargs):
        self.nics = []

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
                        x['addr'] for x in ip_addr
                        ] if ip_addr else None,  # FIXME: handle IPv6 addresses
                    'ethtool': self._ethtool_for_interface(interface)
                }
                self.nics.append(nic)

    def get_network_cards(self):
        return self.nics

    def get_netbox_network_cards(self):
        pass

    def update_netbox_network_cards(self):
        # if network doesn't exist we create it
        if True:
            pass
        # or we check if it needs update
        else:
            pass
