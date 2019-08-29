import subprocess


class LLDP():
    def __init__(self):
        self.output = subprocess.getoutput('lldpctl -f keyvalue')
        self.data = self.parse()

    def parse(self):
        output_dict = {}
        for entry in self.output.splitlines():
            if '=' not in entry:
                continue
            path, value = entry.strip().split("=", 1)
            path = path.split(".")
            path_components, final = path[:-1], path[-1]

            current_dict = output_dict
            for path_component in path_components:
                current_dict[path_component] = current_dict.get(path_component, {})
                current_dict = current_dict[path_component]
            current_dict[final] = value
        return output_dict

    def get_switch_ip(self, interface):
        # lldp.eth0.chassis.mgmt-ip=100.66.7.222
        if self.data['lldp'].get(interface) is None:
            return None
        return self.data['lldp'][interface]['chassis']['mgmt-ip']

    def get_switch_port(self, interface):
        # lldp.eth0.port.descr=GigabitEthernet1/0/1
        if self.data['lldp'].get(interface) is None:
            return None
        return self.data['lldp'][interface]['port']['descr']

    def get_switch_vlan(self, interface):
        # lldp.eth0.vlan.vlan-id=296
        if self.data['lldp'].get(interface) is None:
            return None

        lldp = self.data['lldp'][interface]
        if lldp.get('vlan'):
            if type(lldp['vlan']) is str:
                return int(lldp['vlan'].replace('vlan-', ''))
            elif lldp['vlan'].get('vlan-id'):
                return int(lldp['vlan'].get('vlan-id'))
        return None
