from netbox_agent.location import Slot
from netbox_agent.server import ServerBase
from netbox_agent.misc import is_tool
from netbox_agent.config import config
import subprocess

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
        product_name = self.system[0]['Product Name'].strip()
        # Blades
        blade = product_name.startswith('SBI')
        blade |= product_name.startswith('SBA')
        # Twin
        blade |= 'TR-' in product_name
        # TwinPro
        blade |= 'TP-' in product_name
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
        if self.is_blade():
            return self.baseboard[0]['Serial Number'].strip()
        # some servers model or seller set Hardware system serial as ["123456789", "0123456789"] instead default from manufacture
        # in this case, we'll read from FRU instead 
        if self.system[0]['Serial Number'].strip() in config.device.ignore_serial_number:
            return self.get_fru().strip()
        return self.system[0]['Serial Number'].strip()

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

    def get_expansion_product(self):
        """
        Get the extension slot that is on a pair slot number
        next to the compute slot that is on an odd slot number
        I only know on model of slot GPU extension card that.
        """
        raise NotImplementedError
    def get_fru(self):
        if not is_tool('IPMICFG'):
            logging.error('IPMICFG does not seem to be present on your system. Add it your path or '
                        'check the compatibility of this project with your distro.')
            sys.exit(1)
        return subprocess.getoutput('IPMICFG -fru PS')
