import importlib
import importlib.machinery

from netbox_agent.config import DATACENTER_LOCATION, DATACENTER_LOCATION_DRIVER_FILE, \
    DATACENTER_LOCATION_REGEX


class Datacenter():
    """
    """
    def __init__(self, *args, **kwargs):
        self.driver = DATACENTER_LOCATION.split(':')[0]
        self.driver_value = DATACENTER_LOCATION.split(':')[1]
        self.driver_file = DATACENTER_LOCATION_DRIVER_FILE

        if self.driver_file:
            try:
                # FIXME: Works with Python 3.3+, support older version?
                loader = importlib.machinery.SourceFileLoader('driver_file', self.driver_file)
                self.driver = loader.load_module()
            except ImportError:
                raise ImportError("Couldn't import {} as a module".format(self.driver_file))
        else:
            try:
                self.driver = importlib.import_module(
                    'netbox_agent.drivers.datacenter_{}'.format(self.driver)
                )
            except ImportError:
                raise ImportError("Driver {} doesn't exists".format(self.driver))

    def get(self):
        return getattr(self.driver, 'get')(self.driver_value, DATACENTER_LOCATION_REGEX)
