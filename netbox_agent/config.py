import logging
import sys

import jsonargparse
import pynetbox


def get_config():
    p = jsonargparse.ArgumentParser(
        default_config_files=[
            '/etc/netbox_agent.yaml',
            '~/.config/netbox_agent.yaml',
            '~/.netbox_agent.yaml',
        ],
        prog='netbox_agent',
        description="Netbox agent to run on your infrastructure's servers",
        env_prefix='NETBOX_AGENT_',
        default_env=True
    )
    p.add_argument('-c', '--config', action=jsonargparse.ActionConfigFile)

    p.add_argument('-r', '--register', action='store_true', help='Register server to Netbox')
    p.add_argument('-u', '--update-all', action='store_true', help='Update all infos in Netbox')
    p.add_argument('-d', '--debug', action='store_true', help='Print debug infos')
    p.add_argument('--update-network', action='store_true', help='Update network')
    p.add_argument('--update-inventory', action='store_true', help='Update inventory')
    p.add_argument('--update-location', action='store_true', help='Update location')
    p.add_argument('--update-psu', action='store_true', help='Update PSU')

    p.add_argument('--log_level', default='debug')
    p.add_argument('--netbox.url', help='Netbox URL')
    p.add_argument('--netbox.token', help='Netbox API Token')
    p.add_argument('--virtual.enabled', action='store_true', help='Is a virtual machine or not')
    p.add_argument('--virtual.cluster_name', help='Cluster name of VM')
    p.add_argument('--hostname_cmd', default=None,
                   help="Command to output hostname, used as Device's name in netbox")
    p.add_argument('--datacenter_location.driver',
                   help='Datacenter location driver, ie: cmd, file')
    p.add_argument('--datacenter_location.driver_file',
                   help='Datacenter location custom driver file path')
    p.add_argument('--datacenter_location.regex',
                   help='Datacenter location regex to extract Netbox DC slug')
    p.add_argument('--rack_location.driver', help='Rack location driver, ie: cmd, file')
    p.add_argument('--rack_location.driver_file', help='Rack location custom driver file path')
    p.add_argument('--rack_location.regex', help='Rack location regex to extract Rack name')
    p.add_argument('--slot_location.driver', help='Slot location driver, ie: cmd, file')
    p.add_argument('--slot_location.driver_file', help='Slot location custom driver file path')
    p.add_argument('--slot_location.regex', help='Slot location regex to extract slot name')
    p.add_argument('--network.ignore_interfaces', default=r'(dummy.*|docker.*)',
                   help='Regex to ignore interfaces')
    p.add_argument('--network.ignore_ips', default=r'^(127\.0\.0\..*|fe80.*|::1.*)',
                   help='Regex to ignore IPs')
    p.add_argument('--network.lldp', help='Enable auto-cabling feature through LLDP infos')
    p.add_argument('--inventory', action='store_true',
                   help='Enable HW inventory (CPU, Memory, RAID Cards, Disks) feature')

    options = p.parse_args()
    return options


def get_netbox_instance():
    config = get_config()
    if config.netbox.url is None or config.netbox.token is None:
        logging.error('Netbox URL and token are mandatory')
        sys.exit(1)
    return pynetbox.api(
        url=get_config().netbox.url,
        token=get_config().netbox.token,
    )


config = get_config()
netbox_instance = get_netbox_instance()
