from shutil import which


def is_tool(name):
    '''Check whether `name` is on PATH and marked as executable.'''
    return which(name) is not None


def get_vendor(name):
    vendors = {
        'ST': 'Seagate',
        'Crucial': 'Crucial',
        'Micron': 'Micron',
        'Intel': 'Intel',
        'Samsung': 'Samsung',
        'HGST': 'HGST',
        }
    for key, value in vendors.items():
        if name.startswith(key):
            return value
    return name
