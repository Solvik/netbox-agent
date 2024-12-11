from netbox_agent.server import ServerBase


class QCTHost(ServerBase):
    def __init__(self, *args, **kwargs):
        super(QCTHost, self).__init__(*args, **kwargs)
        self.manufacturer = "QCT"

    def is_blade(self):
        return "Location In Chassis" in self.baseboard[0].keys()

    def get_blade_slot(self):
        if self.is_blade():
            return "Slot {}".format(self.baseboard[0].get("Location In Chassis").strip())
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
