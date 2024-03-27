import re
import netbox_agent.dmidecode as dmidecode
import netbox_agent.misc as misc
from netbox_agent.server import ServerBase


class HetznerHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(HetznerHost, self).__init__(*args, **kwargs)
        self.manufacturer = "Hetzner"

    def is_blade(self):
        return False

    def get_blade_slot(self):
        return None

    def get_chassis_name(self):
        return None

    def get_chassis(self):
        return self.get_product_name()

    def get_chassis_service_tag(self):
        """
        Validates a chassis service tag to ensure it contains 1 to 12 alphanumeric characters with at least one digit.

        Returns:
            str: The validated chassis service tag if it meets the criteria, otherwise returns the hostname of the machine.
        """

        if misc.verify_serial(self.get_service_tag()):
            return self.get_service_tag()

        return self.get_hostname()

