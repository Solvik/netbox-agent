import importlib
import importlib.machinery

from netbox_agent.config import DATACENTER_LOCATION, DATACENTER_LOCATION_DRIVER_FILE, \
    DATACENTER_LOCATION_REGEX, RACK_LOCATION, RACK_LOCATION_DRIVER_FILE, RACK_LOCATION_REGEX, \
    SLOT_LOCATION, SLOT_LOCATION_DRIVER_FILE, SLOT_LOCATION_REGEX


class LocationBase():
    """
    This class is used to guess the location in order to push the information
    in Netbox for a `Device`

    A driver takes a `value` and evaluates a regex with a `capture group`.

    There's embeded drivers such as `file` or `cmd` which read a file or return the
    output of a file.

    There's also a support for an external driver file outside of this project in case
    the logic isn't supported here.
    """
    def __init__(self, driver, driver_value, driver_file, regex, *args, **kwargs):
        self.driver = driver
        self.driver_value = driver_value
        self.driver_file = driver_file
        self.regex = regex

        if self.driver_file:
            try:
                # FIXME: Works with Python 3.3+, support older version?
                loader = importlib.machinery.SourceFileLoader('driver_file', self.driver_file)
                self.driver = loader.load_module()
            except ImportError:
                raise ImportError("Couldn't import {} as a module".format(self.driver_file))
        else:
            if self.driver:
                try:
                    self.driver = importlib.import_module(
                        'netbox_agent.drivers.{}'.format(self.driver)
                    )
                except ImportError:
                    raise ImportError("Driver {} doesn't exists".format(self.driver))

    def get(self):
        if self.driver is None:
            return None
        if not hasattr(self.driver, 'get'):
            raise Exception(
                "Your driver {} doesn't have a get() function, please fix it".format(self.driver)
            )
        return getattr(self.driver, 'get')(self.driver_value, self.regex)


class Datacenter(LocationBase):
    def __init__(self):
        driver = DATACENTER_LOCATION.split(':')[0] if DATACENTER_LOCATION else None
        driver_value = ':'.join(DATACENTER_LOCATION.split(':')[1:]) if DATACENTER_LOCATION \
            else None
        driver_file = DATACENTER_LOCATION_DRIVER_FILE
        regex = DATACENTER_LOCATION_REGEX
        super().__init__(driver, driver_value, driver_file, regex)


class Rack(LocationBase):
    def __init__(self):
        driver = RACK_LOCATION.split(':')[0] if RACK_LOCATION else None
        driver_value = ':'.join(RACK_LOCATION.split(':')[1:]) if RACK_LOCATION else None
        driver_file = RACK_LOCATION_DRIVER_FILE
        regex = RACK_LOCATION_REGEX
        super().__init__(driver, driver_value, driver_file, regex)


class Slot(LocationBase):
    def __init__(self):
        driver = SLOT_LOCATION.split(':')[0] if SLOT_LOCATION else None
        driver_value = ':'.join(SLOT_LOCATION.split(':')[1:]) if SLOT_LOCATION else None
        driver_file = SLOT_LOCATION_DRIVER_FILE
        regex = SLOT_LOCATION_REGEX
        super().__init__(driver, driver_value, driver_file, regex)
