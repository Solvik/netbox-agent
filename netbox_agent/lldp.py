import subprocess


class LLDP():
    def __init__(self, output=None):
        if output:
            self.output = output
        else:
            self.output = subprocess.getoutput('lldpctl -f keyvalue')
        self.data = self.parse()

    def parse(self):
        output_dict = {}
        vlans = {}
        vid = None
        for entry in self.output.splitlines():
            if '=' not in entry:
                continue
            path, value = entry.strip().split("=", 1)
            split_path = path.split(".")
            interface = split_path[1]
            path_components, final = split_path[:-1], split_path[-1]
            current_dict = output_dict

            if vlans.get(interface) is None:
                vlans[interface] = {}

            for path_component in path_components:
                current_dict[path_component] = current_dict.get(path_component, {})
                current_dict = current_dict[path_component]
                if 'vlan-id' in path:
                    vid = value
                    vlans[interface][value] = vlans[interface].get(vid, {})
                elif path.endswith('vlan'):
                    vid = value.replace('vlan-', '')
                    vlans[interface][vid] = vlans[interface].get(vid, {})
                elif 'pvid' in path:
                    vlans[interface][vid]['pvid'] = True
            if 'vlan' not in path:
                current_dict[final] = value
        for interface, vlan in vlans.items():
            output_dict['lldp'][interface]['vlan'] = vlan
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
        if self.data['lldp'][interface]['port'].get('ifname'):
            return self.data['lldp'][interface]['port']['ifname']
        return self.data['lldp'][interface]['port']['descr']

    def get_switch_vlan(self, interface):
        # lldp.eth0.vlan.vlan-id=296
        if self.data['lldp'].get(interface) is None:
            return None
        return self.data['lldp'][interface]['vlan']
