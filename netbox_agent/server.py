import re
import os
from netbox_agent.dmidecode import Dmidecode

# Regex to match base interface name
# Doesn't match vlan interfaces and other loopback etc
INTERFACE_REGEX = re.compile('^(eth[0-9]+|ens[0-9]+|enp[0-9]+s[0-9]f[0-9])$')

class ServerBase():
    def __init__(self, dmi=None):
        if dmi:
            self.dmi = dmi
        else:
            self.dmi = Dmidecode()
        self.system = self.dmi.get('system')
        self.bios = self.dmi.get('bios')

        self.network_cards = []

    def get_product_name(self):
        '''
        Return the Chassis Name from dmidecode info
        '''
        return self.system[0]['Product Name']

    def get_service_tag(self):
        '''
        Return the Service Tag from dmidecode info
        '''
        return self.system[0]['Serial Number']

    def is_blade(self):
        raise NotImplementedError

    def get_blade_slot(self):
        raise NotImplementedError

    def get_chassis(self):
        raise NotImplementedError

    def get_chassis_service_tag(self):
        raise NotImplementedError

    def get_bios_version(self):
        raise NotImplementedError

    def get_bios_version_attr(self):
        raise NotImplementedError

    def get_bios_release_date(self):
        raise NotImplementedError

    def get_network_cards(self):
        nics = []
        for interface in os.listdir('/sys/class/net/'):
            if re.match(INTERFACE_REGEX, interface):
                nic = {
                    'name': interface,
                    'mac': open('/sys/class/net/{}/address'.format(interface), 'r').read().strip(),
                    'ip': None, #FIXME
                }
                nics.append(nic)
        return nics
