from pprint import pprint
import socket

from netbox_agent.config import netbox_instance as nb
from netbox_agent.datacenter import Datacenter
import netbox_agent.dmidecode as dmidecode
from netbox_agent.network import Network


class ServerBase():
    def __init__(self, dmi=None):
        if dmi:
            self.dmi = dmi
        else:
            self.dmi = dmidecode.parse()
        self.system = self.dmi.get_by_type('System')
        self.bios = self.dmi.get_by_type('BIOS')

        self.network = Network(server=self)

    def get_datacenter(self):
        dc = Datacenter()
        return dc.get()

    def get_netbox_datacenter(self):
        datacenter = nb.dcim.sites.get(
            slug=self.get_datacenter()
        )
        return datacenter

    def get_product_name(self):
        """
        Return the Chassis Name from dmidecode info
        """
        return self.system[0]['Product Name']

    def get_service_tag(self):
        """
        Return the Service Tag from dmidecode info
        """
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

    def _netbox_create_blade_chassis(self):
        device_type = nb.dcim.device_types.get(
            model=self.get_chassis(),
        )
        if not device_type:
            raise Exception('Chassis "{}" doesn\'t exist'.format(self.get_chassis()))
        device_role = nb.dcim.device_roles.get(
            name='Server Chassis',
        )
        new_chassis = nb.dcim.devices.create(
            name=''.format(),
            device_type=device_type.id,
            serial=self.get_chassis_service_tag(),
            device_role=device_role.id,
            site=datacenter.id if datacenter else None,
        )
        return new_chassis

    def _netbox_create_blade(self, chassis, datacenter):
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
            site=datacenter.id if datacenter else None,
        )
        return new_blade

    def _netbox_create_server(self, datacenter):
        device_role = nb.dcim.device_roles.get(
            name='Server',
        )
        device_type = nb.dcim.device_types.get(
            model=self.get_product_name(),
        )
        if not device_type:
            raise Exception('Chassis "{}" doesn\'t exist'.format(self.get_chassis()))
        new_server = nb.dcim.devices.create(
            name='{}'.format(socket.gethostname()),
            serial=self.get_service_tag(),
            device_role=device_role.id,
            device_type=device_type.id,
            site=datacenter.id if datacenter else None,
        )
        return new_server

    def get_netbox_server(self):
        return nb.dcim.devices.get(serial=self.get_service_tag())

    def netbox_create(self):
        datacenter = self.get_netbox_datacenter()
        if self.is_blade():
            # let's find the blade
            blade = nb.dcim.devices.get(serial=self.get_service_tag())
            chassis = nb.dcim.devices.get(serial=self.get_chassis_service_tag())
            # if it doesn't exist, create it
            if not blade:
                # check if the chassis exist before
                # if it doesn't exist, create it
                if not chassis:
                    chassis = self._netbox_create_blade_chassis(datacenter)

                blade = self._netbox_create_blade(chassis, datacenter)

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
            server = nb.dcim.devices.get(serial=self.get_service_tag())
            if not server:
                self._netbox_create_server()

        self.network.update_netbox_network_cards()

    def print_debug(self):
        # FIXME: do something more generic by looping on every get_* methods
        print('Datacenter:', self.get_datacenter())
        print('Netbox Datacenter:', self.get_netbox_datacenter())
        print('Is blade:', self.is_blade())
        print('Product Name:', self.get_product_name())
        print('Chassis:', self.get_chassis())
        print('Chassis service tag:', self.get_chassis_service_tag())
        print('Service tag:', self.get_service_tag())
        print('NIC:',)
        pprint(self.network.get_network_cards())
        pass
