import re
import subprocess
from shutil import which

from netbox_agent.config import config

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

        fields = {
            "speed": "-",
            "max_speed": "-",
            "link": "-",
            "duplex": "-",
        }
        field = ""
        for line in output.split("\n")[1:]:
            line = line.rstrip()
            r = line.find(":")
            if r > 0:
                field = line[:r].strip()
                if field not in field_map:
                    continue
                field_key = field_map[field]
                output = line[r + 1 :].strip()
                fields[field_key] = output
            else:
                if len(field) > 0 and field in field_map:
                    field_key = field_map[field]
                    fields[field_key] += " " + line.strip()

        numbers = re.compile(r"\d+")
        supported_speeds = [
            int(match.group(0)) for match in numbers.finditer(fields.get("sup_link_modes", ""))
        ]
        if supported_speeds:
            fields["max_speed"] = "{}Mb/s".format(max(supported_speeds))

        for k in ("speed", "duplex"):
            if fields[k].startswith("Unknown!"):
                fields[k] = "-"

        return fields

    def _parse_ethtool_module_output(self):
        status, output = subprocess.getstatusoutput("ethtool -m {}".format(self.interface))
        if status == 0:
            r = re.search(r"Identifier.*\((\w+)\)", output)
            if r and len(r.groups()) > 0:
                return {"form_factor": r.groups()[0]}
        return {}

    def parse_ethtool_mac_output(self):
        status, output = subprocess.getstatusoutput("ethtool -P {}".format(self.interface))
        if status == 0:
            match = re.search(r"[0-9a-f:]{17}", output)
            if match and match.group(0) != "00:00:00:00:00:00":
                return {"mac_address": match.group(0)}
        return {}

    def parse(self):
        if which("ethtool") is None:
            return None
        output = self._parse_ethtool_output()
        output.update(self._parse_ethtool_module_output())
        output.update(self.parse_ethtool_mac_output())
        return output
