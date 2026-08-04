import re
import subprocess


class Ifconfig:
    """Parse ``ifconfig -a`` output.

    Used on systems without Linux sysfs (``/sys/class/net``) -- e.g. *BSD -- to
    provide the per-interface facts that :class:`~netbox_agent.network.Network`
    otherwise reads from ``/sys``: the hardware (MAC) address and the MTU.

    Pass ``output`` to parse a captured string (used by the tests); otherwise it
    runs ``ifconfig -a`` itself.
    """

    def __init__(self, output=None):
        if output is None:
            output = subprocess.getoutput("ifconfig -a")
        self.output = output
        self.interfaces = self.parse()

    def parse(self):
        interfaces = {}
        current = None
        for line in self.output.splitlines():
            # Interface header lines start in column 0, e.g.
            #   vtnet0: flags=1008843<UP,BROADCAST,...> metric 0 mtu 1500
            header = re.match(r"^(\S+?): flags=\S*<[^>]*>(.*)$", line)
            if header:
                current = header.group(1)
                mtu = re.search(r"\bmtu (\d+)", header.group(2))
                interfaces[current] = {
                    "mac": None,
                    "mtu": int(mtu.group(1)) if mtu else None,
                }
                continue
            if current is None:
                continue
            # Indented link-layer line carries the MAC, e.g.
            #   "\tether bc:24:11:6e:21:cd"
            ether = re.match(r"\s+ether ([0-9a-fA-F:]{17})\b", line)
            if ether:
                interfaces[current]["mac"] = ether.group(1)
        return interfaces
