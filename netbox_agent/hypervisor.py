import subprocess

from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb


class Hypervisor:
    def __init__(self, server=None):
        self.server = server
        self.netbox_server = self.server.get_netbox_server()

    def get_netbox_cluster(self, name):
        cluster = nb.virtualization.clusters.get(
            name=name,
        )
        return cluster

    def create_or_update_device_cluster(self):
        cluster = self.get_netbox_cluster(config.virtual.cluster_name)
        if self.netbox_server.cluster != cluster:
            self.netbox_server.cluster = cluster
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

    def create_netbox_virtual_guest(self, name):
        guest = nb.virtualization.virtual_machines.create(
            name=name,
            device=self.netbox_server.id,
            cluster=self.netbox_server.cluster.id,
        )
        return guest

    def get_virtual_guests(self):
        status, output = subprocess.getstatusoutput(config.virtual.list_guests_cmd)

        if status == 0:
            return output.split()
        else:
            raise Exception(f"Error occurred while executing the command: {output}")

    def create_or_update_device_virtual_machines(self):
        nb_guests = self.get_netbox_virtual_guests()
        guests = self.get_virtual_guests()

        for nb_guest in nb_guests:
            # loop over the VMs associated to this hypervisor in Netbox
            if nb_guest.name not in guests:
                # remove the device property from VMs not found on the hypervisor
                nb_guest.device = None
                nb_guest.save()

        for guest in guests:
            # loop over the VMs running in this hypervisor
            nb_guest = self.get_netbox_virtual_guest(guest)
            if not nb_guest:
                # add the VM to Netbox
                nb.virtualization.virtual_machines
                nb_guest = self.create_netbox_virtual_guest(guest)
            if nb_guest.device != self.netbox_server:
                # add the device property to VMs found on the hypervisor
                nb_guest.device = self.netbox_server
                nb_guest.save()

        return True
