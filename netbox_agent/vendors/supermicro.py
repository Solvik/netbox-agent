
from netbox_agent.location import Slot
from netbox_agent.server import ServerBase


"""
 Supermicro DMI can be messed up.  They depend on the vendor
 to set the correct values.  The endusers cannot
 change them without buying a license from Supermicro.

 There are 3 serial numbers in the system

   1) System - this is used for the chassis information.
   2) Baseboard - this is used for the blade.
   3) Chassis - this is ignored.

"""


class SupermicroHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(SupermicroHost, self).__init__(*args, **kwargs)
        self.manufacturer = 'Supermicro'

    def is_blade(self):
        blade = self.system[0]['Product Name'].startswith('SBI')
        blade |= self.system[0]['Product Name'].startswith('SYS')
        return blade

    def get_blade_slot(self):
        if self.is_blade():
            # Some Supermicro servers don't report the slot in dmidecode
            # let's use a regex
            slot = Slot()
            return slot.get()
        # No supermicro on hands
        return None

    def get_service_tag(self):
        return self.baseboard[0]['Serial Number'].strip()

    def get_product_name(self):
        if self.is_blade():
            return self.baseboard[0]['Product Name'].strip()
        return self.system[0]['Product Name'].strip()

    def get_chassis(self):
        if self.is_blade():
            return self.system[0]['Product Name'].strip()
        return self.get_product_name()

    def get_chassis_service_tag(self):
        if self.is_blade():
            return self.system[0]['Serial Number'].strip()
        return self.get_service_tag()

    def get_chassis_name(self):
        if not self.is_blade():
            return None
        return 'Chassis {}'.format(self.get_chassis_service_tag())
