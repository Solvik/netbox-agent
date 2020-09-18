import netbox_agent.dmidecode as dmidecode
from netbox_agent.server import ServerBase


class HPHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(HPHost, self).__init__(*args, **kwargs)
        self.manufacturer = "HP"
        self.product = self.get_product_name()
        if self.is_blade():
            self.hp_rack_locator = self._find_rack_locator()

    def is_blade(self):
        blade = self.product.startswith("ProLiant BL")
        blade |= self.product.startswith("ProLiant m") and self.product.endswith("Server Cartridge")
        return blade

    def _find_rack_locator(self):
        """
        Depending on the server, the type of the `HP ProLiant System/Rack Locator`
        can change.
        So we need to find it every time
        """
        # FIXME: make a dmidecode function get_by_dminame() ?
        if self.is_blade():
            locator = dmidecode.get_by_type(self.dmi, 204)
            if self.product.startswith("ProLiant BL460c Gen10"):
                locator = locator[0]["Strings"]
                return {
                    "Enclosure Model": locator[2].strip(),
                    "Enclosure Name": locator[0].strip(),
                    "Server Bay": locator[3].strip(),
                    "Enclosure Serial": locator[4].strip(),
                }

            # HP ProLiant m750, m710x, m510 Server Cartridge
            if self.product.startswith("ProLiant m") and self.product.endswith("Server Cartridge"):
                locator = dmidecode.get_by_type(self.dmi, 2)
                chassis = dmidecode.get_by_type(self.dmi, 3)
                return {
                    "Enclosure Model": "Moonshot 1500 Chassis",
                    "Enclosure Name": "Unknown",
                    "Server Bay": locator[0]["Location In Chassis"].strip(),
                    "Enclosure Serial": chassis[0]["Serial Number"].strip(),
                }

            return locator[0]

    def get_blade_slot(self):
        if self.is_blade():
            return "Bay {}".format(str(self.hp_rack_locator["Server Bay"].strip()))
        return None

    def get_chassis(self):
        if self.is_blade():
            return self.hp_rack_locator["Enclosure Model"].strip()
        return self.get_product_name()

    def get_chassis_name(self):
        if not self.is_blade():
            return None
        return self.hp_rack_locator["Enclosure Name"].strip()

    def get_chassis_service_tag(self):
        if self.is_blade():
            return self.hp_rack_locator["Enclosure Serial"].strip()
        return self.get_service_tag()

    def get_expansion_product(self):
        """
        Get the extension slot that is on a pair slot number
        next to the compute slot that is on an odd slot number
        I only know on model of slot GPU extension card that.
        """
        if self.own_expansion_slot():
            return "ProLiant BL460c Graphics Expansion Blade"
        return None

    def is_expansion_slot(self, server):
        """
        Return True if its an extension slot, based on the name
        """
        return server.name.endswith(" expansion")

    def get_blade_expansion_slot(self):
        """
        Expansion slot are always the compute bay number + 1
        """
        if self.is_blade() and self.own_expansion_slot():
            return 'Bay {}'.format(
                str(int(self.hp_rack_locator['Server Bay'].strip()) + 1)
            )
        return None

    def own_expansion_slot(self):
        """
        Say if the device can host an extension card based
        on the product name
        """
        return self.get_product_name().endswith('Graphics Exp')
