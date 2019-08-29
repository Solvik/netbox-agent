from netbox_agent.location import Slot
from netbox_agent.server import ServerBase


class SupermicroHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(SupermicroHost, self).__init__(*args, **kwargs)
        self.manufacturer = 'Supermicro'

    def is_blade(self):
        blade = self.get_product_name().startswith('SBI')
        blade |= self.get_product_name().startswith('SYS')
        return blade

    def get_blade_slot(self):
        if self.is_blade():
            # Some Supermicro servers don't report the slot in dmidecode
            # let's use a regex
            slot = Slot()
            return slot.get()
        # No supermicro on hands
        return None

    def get_chassis_name(self):
        if not self.is_blade():
            return None
        return 'Chassis {}'.format(self.get_service_tag())

    def get_chassis(self):
        if self.is_blade():
            return self.dmi.get_by_type('Chassis')[0]['Version']
        return self.get_product_name()

    def get_chassis_service_tag(self):
        if self.is_blade():
            return self.dmi.get_by_type('Chassis')[0]['Serial Number']
        return self.get_service_tag()
