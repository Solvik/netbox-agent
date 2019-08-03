import re
import os
import socket
import netbox_agent.dmidecode as dmidecode
from netbox_agent.config import netbox_instance as nb

# Regex to match base interface name
# Doesn't match vlan interfaces and other loopback etc
INTERFACE_REGEX = re.compile('^(eth[0-9]+|ens[0-9]+|enp[0-9]+s[0-9]f[0-9])$')

class ServerBase():
    def __init__(self, dmi=None):
        if dmi:
            self.dmi = dmi
        else:
            self.dmi = dmidecode.parse()
        self.system = self.dmi.get_by_type('System')
        self.bios = self.dmi.get_by_type('BIOS')

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

    def _netbox_create_blade_chassis(self):
        device_type = nb.dcim.device_types.get(
            model=self.get_chassis(),
        )
        if not device_type:
            raise Exception('Chassis "{}" doesn\'t exist'.format(self.get_chassis()))
        device_role = nb.dcim.device_roles.get(
            name='Server Chassis',
        )
        datacenter = nb.dcim.sites.get(
            name='DC3'
        )
        new_chassis = nb.dcim.devices.create(
            name=''.format(),
            device_type=device_type.id,
            serial=self.get_chassis_service_tag(),
            device_role=device_role.id,
            site=datacenter.id,
        )
        return new_chassis

    def _netbox_create_blade(self, chassis):
        device_role = nb.dcim.device_roles.get(
            name='Blade',
        )
        device_type = nb.dcim.device_types.get(
            model=self.get_product_name(),
        )

        new_blade = nb.dcim.devices.create(
            name='{}'.format(socket.gethostname()),
            serial=self.get_service_tag(),
            device_role=device_role.id,
            device_type=device_type.id,
            parent_device=chassis.id,
            site='1',
        )
        return new_blade

    def netbox_create(self):
        if self.is_blade():
            # let's find the blade
            blade = nb.dcim.devices.get(serial=self.get_service_tag())
            chassis = nb.dcim.devices.get(serial=self.get_chassis_service_tag())
            # if it doesn't exist, create it
            if not blade:
                # check if the chassis exist before
                # if it doesn't exist, create it
                if not chassis:
                    chassis = self._netbox_create_blade_chassis()

                blade = self._netbox_create_blade(chassis)

            # Find the slot and update it with our blade
            device_bays = nb.dcim.device_bays.filter(
                device_id=chassis.id,
                name='Blade {}'.format(self.get_blade_slot()),
                )
            if len(device_bays) > 0:
                device_bay = device_bays[0]
                device_bay.installed_device = blade
                device_bay.save()
        else:
            # FIXME : handle pizza box
            pass
