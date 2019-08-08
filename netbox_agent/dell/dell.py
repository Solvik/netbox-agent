from netbox_agent.server import ServerBase


class DellHost(ServerBase):
    def is_blade(self):
        return self.get_product_name().startswith('PowerEdge M')

    def get_blade_slot(self):
        """
        Return blade slot
        dmidecode output is:
        `        Location In Chassis: Slot 03`
        """
        if self.is_blade():
            return self.dmi.get_by_type('Baseboard')[0].get('Location In Chassis')
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
            return self.dmi.get_by_type('chassis')[0]['Serial Number']
        return self.get_service_tag()
