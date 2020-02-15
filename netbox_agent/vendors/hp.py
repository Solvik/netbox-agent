import netbox_agent.dmidecode as dmidecode
from netbox_agent.server import ServerBase


class HPHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(HPHost, self).__init__(*args, **kwargs)
        if self.is_blade():
            self.hp_rack_locator = self._find_rack_locator()
        self.manufacturer = 'HP'

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
            locator = dmidecode.get_by_type(self.dmi, 204)
            if self.get_product_name() == 'ProLiant BL460c Gen10':
                locator = locator[0]['Strings']
                return {
                    'Enclosure Model': locator[2].strip(),
                    'Enclosure Name': locator[0].strip(),
                    'Server Bay': locator[3].strip(),
                    'Enclosure Serial': locator[4].strip(),
                }
            return locator[0]

    def get_blade_slot(self):
        if self.is_blade():
            return 'Bay {}'.format(
                int(self.hp_rack_locator['Server Bay'].strip())
            )
        return None

    def get_chassis(self):
        if self.is_blade():
            return self.hp_rack_locator['Enclosure Model'].strip()
        return self.get_product_name()

    def get_chassis_name(self):
        if not self.is_blade():
            return None
        return self.hp_rack_locator['Enclosure Name'].strip()

    def get_chassis_service_tag(self):
        if self.is_blade():
            return self.hp_rack_locator['Enclosure Serial'].strip()
        return self.get_service_tag()
