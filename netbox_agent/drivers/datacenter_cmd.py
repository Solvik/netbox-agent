import re
import subprocess


def get(value, regex):
    output = subprocess.getoutput(value)
    r = re.search(regex, output)
    if r and len(r.groups()) > 0:
        return r.groups()[0]
    return None
