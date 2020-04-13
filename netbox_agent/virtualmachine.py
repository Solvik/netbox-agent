import math
import os

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

    def get_memory(self):
        mem_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')  # e.g. 4015976448
        mem_gib = mem_bytes/(1024.**3)  # e.g. 3.74
        return math.ceil(mem_gib)

    def get_vcpus(self):
        return os.cpu_count()

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

    def netbox_create_or_update(self, config):
        created = False
        updated = 0

        hostname = get_hostname(config)
        vm = self.get_netbox_vm()

        vcpus = self.get_vcpus()
        memory = self.get_memory()
        if not vm:
            logging.debug('Creating Virtual machine..')
            cluster = self.get_netbox_cluster(config.virtual.cluster_name)

            vm = nb.virtualization.virtual_machines.create(
                name=hostname,
                cluster=cluster.id,
                vcpus=vcpus,
                memory=memory,
            )
            created = True

        self.network = VirtualNetwork(server=self)
        self.network.create_or_update_netbox_network_cards()

        if not created and vm.vcpus != vcpus:
            vm.vcpus = vcpus
            updated += 1
        elif not created and vm.memory != memory:
            vm.memory = memory
            updated += 1

        if updated:
            vm.save()
