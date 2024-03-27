import netbox_agent.dmidecode as dmidecode
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
        return 'test'
