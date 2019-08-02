import socket
from pprint import pprint

from netbox_agent.server import ServerBase
from netbox_agent.config import netbox_instance as nb

class DellHost(ServerBase):
    def is_blade(self):
        return self.get_product_name().startswith('PowerEdge M')

    def get_blade_slot(self):
        '''
        Return blade slot
        dmidecode output is: 
        `        Location In Chassis: Slot 03`
        '''
        if self.is_blade():
            return int(self.dmi.get('base board')[0].get('Location In Chassis').split()[1])
        return None

    def get_chassis(self):
        if self.is_blade():
            return self.dmi.get('chassis')[0]['Version']
        return self.get_product_name()

    def get_chassis_service_tag(self):
        if self.is_blade():
            return self.dmi.get('chassis')[0]['Serial Number']
        return self.get_service_tag

    def netbox_create(self):
        if self.is_blade():
            # let's find the bblade
            blade = nb.dcim.devices.get(serial=self.get_service_tag())
            chassis = nb.dcim.devices.get(serial=self.get_chassis_service_tag())
            # if it doesn't exist, create it
            if not blade:
                # check if the chassis exist before
                # if it doesn't exist, create it
                if not chassis:
                    device_type = nb.dcim.device_types.get(
                        model=self.get_chassis(),
                        )
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
                    chassis = new_chassis

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
                blade = new_blade

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
