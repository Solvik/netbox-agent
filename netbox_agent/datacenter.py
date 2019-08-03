import importlib

from netbox_agent.config import DATACENTER_LOCATION, \
    DATACENTER_LOCATION_REGEX


class Datacenter():
    """
    """
    def __init__(self, *args, **kwargs):
        self.driver = DATACENTER_LOCATION.split(':')[0]
        self.driver_value = DATACENTER_LOCATION.split(':')[1]

        try:
            self.driver = importlib.import_module('netbox_agent.drivers.datacenter_' + self.driver)
        except ImportError:
            raise ImportError("Driver {} doesn't exists".format(self.driver))

    def get(self):
        return getattr(self.driver, 'get')(self.driver_value, DATACENTER_LOCATION_REGEX)
