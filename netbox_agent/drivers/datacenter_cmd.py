import re
import subprocess


def get(value, regex):
    output = subprocess.getoutput(value)
    r = re.search(regex, output)
    if r:
        result = r.group('datacenter')
        return result
    return None
