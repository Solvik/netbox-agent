import importlib
import importlib.machinery

from netbox_agent.config import DATACENTER_LOCATION, DATACENTER_LOCATION_DRIVER_FILE, \
    DATACENTER_LOCATION_REGEX


class Datacenter():
    """
    This class is used to guess the datacenter in order to push the information
    in Netbox for a `Device`

    A driver takes a `value` and evaluates a regex with a `named group`: `datacenter`.

    There's embeded drivers such as `file` or `cmd` which read a file or return the
    output of a file.

    There's also a support for an external driver file outside of this project in case
    the logic isn't supported here.
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
        if not hasattr(self.driver, 'get'):
            raise Exception("Your driver {} doesn't have a get() function, please fix it".format(self.driver))
        return getattr(self.driver, 'get')(self.driver_value, DATACENTER_LOCATION_REGEX)
