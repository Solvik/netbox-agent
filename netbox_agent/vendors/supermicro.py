from netbox_agent.location import Slot
from netbox_agent.server import ServerBase


class SupermicroHost(ServerBase):
    """
     Supermicro DMI can be messed up.  They depend on the vendor
     to set the correct values.  The endusers cannot
     change them without buying a license from Supermicro.

     There are 3 serial numbers in the system

       1) System - this is used for the chassis information.
       2) Baseboard - this is used for the blade.
       3) Chassis - this is ignored.

    """

    def __init__(self, *args, **kwargs):
        super(SupermicroHost, self).__init__(*args, **kwargs)
        self.manufacturer = 'Supermicro'

    def is_blade(self):
        product_name = self.get_product_name()
        # Blades
        blade = product_name.startswith('SBI')
        blade |= product_name.startswith('SBA')
        # Twin
        blade |= 'TR-' in product_name
        # BigTwin
        blade |= 'BT-' in product_name
        # Microcloud
        blade |= product_name.startswith('SYS-5039')
        blade |= product_name.startswith('SYS-5038')
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
        return self.system[0]['Serial Number'].strip()

    def get_product_name(self):
        return self.system[0]['Product Name'].strip()

    def get_chassis(self):
        if self.is_blade():
            return self.chassis[0]['Product Name'].strip()
        return self.get_product_name()

    def get_chassis_service_tag(self):
        if self.is_blade():
            return self.chassis[0]['Serial Number'].strip()
        return self.get_service_tag()

    def get_chassis_name(self):
        if not self.is_blade():
            return None
        return 'Chassis {}'.format(self.get_chassis_service_tag())

    def get_expansion_product(self):
        """
        Get the extension slot that is on a pair slot number
        next to the compute slot that is on an odd slot number
        I only know on model of slot GPU extension card that.
        """
        raise NotImplementedError

    def is_expansion_slot(self, server):
        """
        Return True if its an extension slot, based on the name
        """
        raise NotImplementedError

    def get_blade_expansion_slot(self):
        """
        Expansion slot are always the compute bay number + 1
        """
        raise NotImplementedError

    def own_expansion_slot(self):
        """
        Say if the device can host an extension card based
        on the product name
        """
        pass
