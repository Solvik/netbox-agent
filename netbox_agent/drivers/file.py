import re


def get(value, regex):
    for line in open(value, "r"):
        r = re.search(regex, line)
        if r and len(r.groups()) > 0:
            return r.groups()[0]
    return None
