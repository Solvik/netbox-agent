import netbox_agent.dmidecode as dmidecode
from netbox_agent.server import ServerBase


class GenericHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(GenericHost, self).__init__(*args, **kwargs)
        self.manufacturer = dmidecode.get_by_type(self.dmi, 'Baseboard')[0].get('Manufacturer')

    def is_blade(self):
        return None

    def get_blade_slot(self):
        return None

    def get_chassis_name(self):
        return None

    def get_chassis(self):
        return self.get_product_name()

    def get_chassis_service_tag(self):
        return self.get_service_tag()

    def get_expansion_product(self):
        """
        Get the extension slot that is on a pair slot number
        next to the compute slot that is on an odd slot number
        """
        raise NotImplementedError

    def is_expansion_slot(self, server):
        """
        Return True if its an extension slot
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
