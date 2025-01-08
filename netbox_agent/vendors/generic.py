import netbox_agent.dmidecode as dmidecode
from netbox_agent.server import ServerBase


class GenericHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(GenericHost, self).__init__(*args, **kwargs)
        self.manufacturer = dmidecode.get_by_type(self.dmi, "Baseboard")[0].get("Manufacturer")

    def is_blade(self):
        return False

    def get_blade_slot(self):
        return None

    def get_chassis_name(self):
        return None

    def get_chassis(self):
        return self.get_product_name()

    def get_chassis_service_tag(self):
        return self.get_service_tag()
