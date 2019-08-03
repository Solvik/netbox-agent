from netbox_agent.server import ServerBase


class HPHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(HPHost, self).__init__(*args, **kwargs)
        if self.is_blade():
            self.hp_rack_locator = self._find_rack_locator()

    def is_blade(self):
        return self.get_product_name().startswith('ProLiant BL')

    def _find_rack_locator(self):
        """
        Depending on the server, the type of the `HP ProLiant System/Rack Locator`
        can change.
        So we need to find it every time
        """
        # FIXME: make a dmidecode function get_by_dminame() ?
        if self.is_blade():
            for key, value in self.dmi.parse().items():
                if value['DMIName'] == 'HP ProLiant System/Rack Locator':
                    return value

    def get_blade_slot(self):
        if self.is_blade():
            return int(self.hp_rack_locator['Server Bay'].strip())
        return None

    def get_chassis(self):
        if self.is_blade():
            return self.hp_rack_locator['Enclosure Model'].strip()
        return self.get_product_name()

    def get_chassis_service_tag(self):
        if self.is_blade():
            return self.hp_rack_locator['Enclosure Serial'].strip()
        return self.get_service_tag()
