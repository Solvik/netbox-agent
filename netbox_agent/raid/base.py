class RaidController:
    def get_product_name(self):
        raise NotImplementedError

    def get_serial_number(self):
        raise NotImplementedError

    def get_manufacturer(self):
        raise NotImplementedError

    def get_firmware_version(self):
        raise NotImplementedError

    def get_physical_disks(self):
        raise NotImplementedError

    def is_external(self):
        return False


class Raid:
    def get_controllers(self):
        raise NotImplementedError
