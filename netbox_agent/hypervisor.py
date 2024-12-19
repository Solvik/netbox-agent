import re
import subprocess

from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb


def parse_output(command_output):
    parsed_items = []
    pattern = r"^\s*\d+\s+(\S+)"
    lines = command_output.splitlines()

    for line in lines:
        _match = re.match(pattern, line)

        if _match:
            extracted_value = _match.group(1)
            parsed_items.append(extracted_value)

    return parsed_items


class Hypervisor():
    def __init__(self, server=None):
        self.server = server
        self.netbox_server = self.server.get_netbox_server()

    def get_netbox_cluster(self, name):
        cluster = nb.virtualization.clusters.get(
            name=name,
        )   
        return cluster

    def create_or_update_cluster_device(self):
        cluster = self.get_netbox_cluster(config.virtual.cluster_name)

        if self.netbox_server.cluster:
            if self.netbox_server.cluster.id != cluster.id:
                self.netbox_server.cluster = cluster.id
                self.netbox_server.save()
        else:
            self.netbox_server.cluster = cluster.id
            self.netbox_server.save()

        return True

    def get_netbox_virtual_guests(self):
        guests = nb.virtualization.virtual_machines.filter(
            device=self.netbox_server.name,
        )   
        return guests

    def get_netbox_virtual_guest(self, name):
        guest = nb.virtualization.virtual_machines.get(
            name=name,
        )   
        return guest

    def get_virtual_guests(self):
        return subprocess.getoutput(config.virtual.list_guests_cmd)

    def create_or_update_cluster_device_virtual_machines(self):
        nb_guests = self.get_netbox_virtual_guests()
        guests = self.get_virtual_guests()
        guests = parse_output(guests)

        for nb_guest in nb_guests:
            if nb_guest not in guests:
                nb_guest.device = None
                nb_guest.save()

        for guest in guests:
            nb_guest = self.get_netbox_virtual_guest(guest)

            if nb_guest and nb_guest.device != self.netbox_server:
                nb_guest.device = self.netbox_server
                nb_guest.save()

        return True
