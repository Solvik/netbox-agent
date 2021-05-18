import socket
import subprocess
from shutil import which

from slugify import slugify

from netbox_agent.config import netbox_instance as nb


def is_tool(name):
    '''Check whether `name` is on PATH and marked as executable.'''
    return which(name) is not None


def get_device_role(role):
    device_role = nb.dcim.device_roles.get(
        name=role
    )
    if device_role is None:
        raise Exception('DeviceRole "{}" does not exist, please create it'.format(role))
    return device_role


def get_device_type(type):
    device_type = nb.dcim.device_types.get(
        model=type
    )
    if device_type is None:
        raise Exception('DeviceType "{}" does not exist, please create it'.format(type))
    return device_type


def get_vendor(name):
    vendors = {
        'PERC': 'Dell',
        'SANDISK': 'SanDisk',
        'DELL': 'Dell',
        'ST': 'Seagate',
        'CRUCIAL': 'Crucial',
        'MICRON': 'Micron',
        'INTEL': 'Intel',
        'SAMSUNG': 'Samsung',
        'EH0': 'HP',
        'HGST': 'HGST',
        'HUH': 'HGST',
        'MB': 'Toshiba',
        'MC': 'Toshiba',
        'MD': 'Toshiba',
        'MG': 'Toshiba',
        'WD': 'WDC'
    }
    for key, value in vendors.items():
        if name.upper().startswith(key):
            return value
    return name


def get_hostname(config):
    if config.hostname_cmd is None:
        return '{}'.format(socket.gethostname())
    return subprocess.getoutput(config.hostname_cmd)


def create_netbox_tags(tags):
    ret = []
    for tag in tags:
        nb_tag = nb.extras.tags.get(
            name=tag
        )
        if not nb_tag:
            nb_tag = nb.extras.tags.create(
                name=tag,
                slug=slugify(tag),
            )
        ret.append(nb_tag)
    return ret
