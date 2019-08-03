import re


def get(value, regex):
    for line in open(value, 'r'):
        r = re.search(regex, line)
        if r:
            return r.group('datacenter')
    return None
