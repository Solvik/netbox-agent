import pynetbox
import yaml

with open('/etc/netbox_agent.yaml', 'r') as ymlfile:
    # FIXME: validate configuration file
    config = yaml.load(ymlfile)

netbox_instance = pynetbox.api(
    url=config['netbox']['url'],
    token=config['netbox']['token']
)

LOG_LEVEL = config.get('log_level', 'debug')

DATACENTER_LOCATION_DRIVER_FILE = None
DATACENTER_LOCATION = None
DATACENTER_LOCATION_REGEX = None
RACK_LOCATION_DRIVER_FILE = None
RACK_LOCATION = None
RACK_LOCATION_REGEX = None

if config.get('datacenter_location'):
    dc_loc = config.get('datacenter_location')
    DATACENTER_LOCATION_DRIVER_FILE = dc_loc.get('driver_file')
    DATACENTER_LOCATION = dc_loc.get('driver')
    DATACENTER_LOCATION_REGEX = dc_loc.get('regex')

if config.get('rack_location'):
    rack_location = config['rack_location']
    RACK_LOCATION_DRIVER_FILE = rack_location.get('driver_file')
    RACK_LOCATION = rack_location.get('driver')
    RACK_LOCATION_REGEX = rack_location.get('regex')

NETWORK_IGNORE_INTERFACES = None
NETWORK_IGNORE_IPS = None
NETWORK_LLDP = None
if config.get('network'):
    NETWORK_IGNORE_INTERFACES = config['network'].get('ignore_interfaces')
    NETWORK_IGNORE_IPS = config['network'].get('ignore_ips')
    NETWORK_LLDP = config['network'].get('lldp') is True

INVENTORY_ENABLED = config.get('inventory') == True
