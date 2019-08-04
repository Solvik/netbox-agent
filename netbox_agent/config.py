import pynetbox
import yaml

with open('/etc/netbox_agent.yaml', 'r') as ymlfile:
    # FIXME: validate configuration file
    config = yaml.load(ymlfile)

netbox_instance = pynetbox.api(
    url=config['netbox']['url'],
    token=config['netbox']['token']
)


DATACENTER_LOCATION_DRIVER_FILE = config.get('datacenter_location').get('driver_file')
DATACENTER_LOCATION = config.get('datacenter_location').get('driver')
DATACENTER_LOCATION_REGEX = config.get('datacenter_location').get('regex')
