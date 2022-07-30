import logging
import subprocess
import socket

from netbox_agent.misc import is_tool


class LLDP():
    def __init__(self, output=None):
        if not is_tool('lldpctl'):
            logging.debug('lldpd package seems to be missing or daemon not running.')
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
        if not output_dict:
            logging.debug('No LLDP output, please check your network config.')
        return output_dict

    def get_switch_ip(self, interface):
        # lldp.eth0.chassis.mgmt-ip=100.66.7.222
        # lldp.eno1.chassis.name=G4U19 # try to conncet to chassis name instead of mgmt-ip in case ip return None
        if self.data['lldp'].get(interface) is None:
            return None
        if self.data['lldp'][interface]['chassis'].get('mgmt-ip') is None:
            logging.debug("No switch IP found, trying to connect via switch domain name")
            ip = socket.gethostbyname(self.data['lldp'][interface]['chassis'].get('name'))
            return ip
        else:
            return self.data['lldp'][interface]['chassis'].get('mgmt-ip')

    def get_switch_port(self, interface):
        # lldp.eth0.port.descr=GigabitEthernet1/0/1
        # lldp.eno1.port.ifname=gi35
        # Cisco SMB SG300 didn't return canonical_int in case True/False, so add an extra convert to ully expanded name
        # To avoid `ERROR:root:Switch interface gi35 cannot be found`
        # NAPALM result:
        #         "GigabitEthernet35": [
        #     {
        #         "parent_interface": "N/A",
        #         "remote_port": "xx:xx:xx:xx:xx:xx",
        #         "remote_port_description": "eno1",
        #         "remote_chassis_id": "yy:yy:yy:yy:yy:yy",
        #         "remote_system_name": "abc",
        #         "remote_system_description": "Debian GNU/Linux 11 (bullseye)",
        #         "remote_system_capab": [
        #             "B"
        #         ],
        #         "remote_system_enable_capab": [
        #             "B"
        #         ]
        #     }
        # ],
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
