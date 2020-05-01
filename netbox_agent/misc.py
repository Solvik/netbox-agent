import socket
import subprocess
from shutil import which


def is_tool(name):
    '''Check whether `name` is on PATH and marked as executable.'''
    return which(name) is not None


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
