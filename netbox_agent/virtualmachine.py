import os

import netbox_agent.dmidecode as dmidecode
from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.location import Tenant
from netbox_agent.logging import logging  # NOQA
from netbox_agent.misc import create_netbox_tags, get_hostname
from netbox_agent.network import VirtualNetwork


def is_vm(dmi):
    bios = dmidecode.get_by_type(dmi, 'BIOS')
    system = dmidecode.get_by_type(dmi, 'System')

    if 'Hyper-V' in bios[0]['Version'] or \
       'Xen' in bios[0]['Version'] or \
       'Google Compute Engine' in system[0]['Product Name'] or \
       'RHEV Hypervisor' in system[0]['Product Name'] or \
       'VirtualBox' in bios[0]['Version'] or \
       'VMware' in system[0]['Manufacturer']:
        return True
    return False


class VirtualMachine(object):
    def __init__(self, dmi=None):
        if dmi:
            self.dmi = dmi
        else:
            self.dmi = dmidecode.parse()
        self.network = None

        self.tags = list(set(config.device.tags.split(','))) if config.device.tags else []
        if self.tags and len(self.tags):
            create_netbox_tags(self.tags)

    def get_memory(self):
        mem_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')  # e.g. 4015976448
        mem_gib = mem_bytes / (1024.**2)  # e.g. 3.74
        return int(mem_gib)

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

    def get_netbox_datacenter(self, name):
        cluster = self.get_netbox_cluster()
        if cluster.datacenter:
            return cluster.datacenter
        return None

    def get_tenant(self):
        tenant = Tenant()
        return tenant.get()

    def get_netbox_tenant(self):
        tenant = self.get_tenant()
        if tenant is None:
            return None
        nb_tenant = nb.tenancy.tenants.get(
            slug=self.get_tenant()
        )
        return nb_tenant

    def netbox_create_or_update(self, config):
        logging.debug('It\'s a virtual machine')
        created = False
        updated = 0

        hostname = get_hostname(config)
        vm = self.get_netbox_vm()

        vcpus = self.get_vcpus()
        memory = self.get_memory()
        tenant = self.get_netbox_tenant()
        if not vm:
            logging.debug('Creating Virtual machine..')
            cluster = self.get_netbox_cluster(config.virtual.cluster_name)

            vm = nb.virtualization.virtual_machines.create(
                name=hostname,
                cluster=cluster.id,
                vcpus=vcpus,
                memory=memory,
                tenant=tenant.id if tenant else None,
                tags=self.tags,
            )
            created = True

        self.network = VirtualNetwork(server=self)
        self.network.create_or_update_netbox_network_cards()

        if not created:
            if vm.vcpus != vcpus:
                vm.vcpus = vcpus
                updated += 1
            if vm.memory != memory:
                vm.memory = memory
                updated += 1
            if sorted(set(vm.tags)) != sorted(set(self.tags)):
                vm.tags = self.tags
                updated += 1

        if updated:
            vm.save()
