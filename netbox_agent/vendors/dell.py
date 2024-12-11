import logging
import subprocess

from netbox_agent.misc import is_tool
from netbox_agent.server import ServerBase


class DellHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(DellHost, self).__init__(*args, **kwargs)
        self.manufacturer = "Dell"

    def is_blade(self):
        return self.get_product_name().startswith("PowerEdge M")

    def get_blade_slot(self):
        """
        Return blade slot
        dmidecode output is:
        `        Location In Chassis: Slot 03`
        """
        if self.is_blade():
            return self.baseboard[0].get("Location In Chassis").strip()
        return None

    def get_chassis_name(self):
        if not self.is_blade():
            return None
        return "Chassis {}".format(self.get_service_tag())

    def get_chassis(self):
        if self.is_blade():
            return self.chassis[0]["Version"].strip()
        return self.get_product_name()

    def get_chassis_service_tag(self):
        if self.is_blade():
            return self.chassis[0]["Serial Number"].strip()
        return self.get_service_tag()

    def get_power_consumption(self):
        """
        Parse omreport output like this

        Amperage
        PS1 Current 1 : 1.8 A
        PS2 Current 2 : 1.4 A
        """
        value = []

        if not is_tool("omreport"):
            logging.error("omreport does not seem to be installed, please debug")
            return value

        data = subprocess.getoutput("omreport chassis pwrmonitoring")
        amperage = False
        for line in data.splitlines():
            if line.startswith("Amperage"):
                amperage = True
                continue

            if amperage:
                if line.startswith("PS"):
                    amp_value = line.split(":")[1].split()[0]
                    value.append(amp_value)
                else:
                    break

        return value

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
