import subprocess

from shutil import which


class OVS():
    def __init__(self):

        self.fields = {}

        if which('ovs-vsctl') is None:
            print("could not find ovs-vsctl")
            return

        status, output = subprocess.getstatusoutput("sudo ovs-vsctl show")

        if status != 0:
            print("ovs-vsctl failed.")
            return

        for line in output.split('\n'):
            line = line.rstrip()
            r = line.split(" ")[-2:]

            if len(r) < 2:
                self.fields["info"] = {}
                self.fields["info"]["switch_uuid"] = r[0]

            if "Bridge" in r[0]:
                bridge = r[1]
            if "Port" in r[0]:
                port = r[1]
                self.fields[port] = {}
                self.fields[port]["port"] = r[1]
                self.fields[port]["bridge"] = bridge
            if "tag" in r[0]:
                self.fields[port]["vlan"] = r[1]
            if "Interface" in r[0]:
                self.fields[port]["interface"] = r[1]
            if "type" in r[0]:
                self.fields[port]["type"] = r[1]
            if "options" in r[0]:
                self.fields[port]["options"] = r[1]
            if "ovs_version" in r[0]:
                self.fields["info"]["ovs_version"] = r[1]

    def get_info(self, interface):
        for iface in self.fields:
            if "interface" in self.fields[iface]:
                if interface in self.fields[iface]["interface"]:
                    return(self.fields[iface])
