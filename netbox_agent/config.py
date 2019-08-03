import pynetbox
import yaml

with open('/etc/netbox_agent.yaml', 'r') as ymlfile:
    # FIXME: validate configuration file
    config = yaml.load(ymlfile)

netbox_instance = pynetbox.api(
    url=config['netbox']['url'],
    token=config['netbox']['token']
)


DATACENTER_LOCATION = config['datacenter_location']['driver']
DATACENTER_LOCATION_REGEX = config['datacenter_location']['regex']
