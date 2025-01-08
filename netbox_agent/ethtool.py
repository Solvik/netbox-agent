import re
import subprocess
from shutil import which

#  Originally from https://github.com/opencoff/useful-scripts/blob/master/linktest.py

# mapping fields from ethtool output to simple names
field_map = {
    "Supported ports": "ports",
    "Supported link modes": "sup_link_modes",
    "Supports auto-negotiation": "sup_autoneg",
    "Advertised link modes": "adv_link_modes",
    "Advertised auto-negotiation": "adv_autoneg",
    "Speed": "speed",
    "Duplex": "duplex",
    "Port": "port",
    "Auto-negotiation": "autoneg",
    "Link detected": "link",
}


def merge_two_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z


class Ethtool:
    """
    This class aims to parse ethtool output
    There is several bindings to have something proper, but it requires
    compilation and other requirements.
    """

    def __init__(self, interface, *args, **kwargs):
        self.interface = interface

    def _parse_ethtool_output(self):
        """
        parse ethtool output
        """

        output = subprocess.getoutput("ethtool {}".format(self.interface))

        fields = {}
        field = ""
        fields["speed"] = "-"
        fields["link"] = "-"
        fields["duplex"] = "-"
        for line in output.split("\n")[1:]:
            line = line.rstrip()
            r = line.find(":")
            if r > 0:
                field = line[:r].strip()
                if field not in field_map:
                    continue
                field = field_map[field]
                output = line[r + 1 :].strip()
                fields[field] = output
            else:
                if len(field) > 0 and field in field_map:
                    fields[field] += " " + line.strip()
        return fields

    def _parse_ethtool_module_output(self):
        status, output = subprocess.getstatusoutput("ethtool -m {}".format(self.interface))
        if status == 0:
            r = re.search(r"Identifier.*\((\w+)\)", output)
            if r and len(r.groups()) > 0:
                return {"form_factor": r.groups()[0]}
        return {}

    def parse(self):
        if which("ethtool") is None:
            return None
        output = self._parse_ethtool_output()
        output.update(self._parse_ethtool_module_output())
        return output
