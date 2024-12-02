import logging

from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb


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
        if self.netbox_server.cluster.id != cluster.id:
            self.netbox_server.cluster = cluster
            self.netbox_server.save()
        return True

    def get_netbox_virtual_guests(self):
        guests = nb.virtualization.virtual_machines.get(
            device=self.netbox_server.name,
        )   
        return guests

    def get_netbox_virtual_guest(self, name):
        guest = nb.virtualization.virtual_machines.get(
            name=name,
        )   
        return guest

    def get_virtual_guests(self):
        return subprocess.getoutput(config.virtual.list_guests_cmd).split()

    def create_or_update_cluster_device_virtual_machines(self):
        nb_guests = self.get_netbox_virtual_guests()
        guests = self.get_virtual_guests()

        for nb_guest in nb_guests:
            if nb_guest not in guests:
                nb_guest.device = None
                nb.guest.save()

        for guest in guests:
            nb_guest = self.get_netbox_virtual_guest(guest)
            if nb_guest.device != self.netbox_server:
                nb_guest.device = self.netbox_server
                nb.guest.save()

        return True
