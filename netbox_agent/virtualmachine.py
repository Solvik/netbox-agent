import netbox_agent.dmidecode as dmidecode
from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.logging import logging  # NOQA
from netbox_agent.misc import get_hostname
from netbox_agent.network import VirtualNetwork

class VirtualMachine(object):
    def __init__(self, dmi=None):
        if dmi:
            self.dmi = dmi
        else:
            self.dmi = dmidecode.parse()
        self.network = None

    def get_netbox_vm(self):
        hostname = get_hostname(config)
        vm = nb.virtualization.virtual_machines.get(
            name=hostname
        )
        return vm

    def get_netbox_cluster(self, name):
        cluster = nb.virtualization.clusters.get(
            name=name,
            )
        return cluster

    def netbox_create(self, config):
        hostname = get_hostname(config)
        vm = self.get_netbox_vm()

        if not vm:
            logging.debug('Creating Virtual machine..')
            cluster = self.get_netbox_cluster(config.virtual.cluster_name)

            vm = nb.virtualization.virtual_machines.create(
                name=hostname,
                cluster=cluster.id,
                vcpu=0,
                memory=0,
                )
            self.network = VirtualNetwork(server=self)
            self.network.update_netbox_network_cards()
        else:
            self.network = VirtualNetwork(server=self)
            self.network.update_netbox_network_cards()
