import os

import netbox_agent.dmidecode as dmidecode
from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.location import Tenant
from netbox_agent.logging import logging  # NOQA
from netbox_agent.misc import create_netbox_tags, get_hostname, get_device_platform
from netbox_agent.network import VirtualNetwork
from pprint import pprint


def is_vm(dmi):
    bios = dmidecode.get_by_type(dmi, "BIOS")[0]
    system = dmidecode.get_by_type(dmi, "System")[0]

    return (
        "Hyper-V" in bios["Version"]
        or "Xen" in bios["Version"]
        or "Google Compute Engine" in system["Product Name"]
    ) or (
        ("Amazon EC2" in system["Manufacturer"] and not system["Product Name"].endswith(".metal"))
        or "RHEV Hypervisor" in system["Product Name"]
        or "QEMU" in system["Manufacturer"]
        or "VirtualBox" in bios["Version"]
        or "VMware" in system["Manufacturer"]
    )


class VirtualMachine(object):
    def __init__(self, dmi=None):
        if dmi:
            self.dmi = dmi
        else:
            self.dmi = dmidecode.parse()
        self.network = None
        self.device_platform = get_device_platform(config.device.platform)

        self.tags = list(set(config.device.tags.split(","))) if config.device.tags else []
        self.nb_tags = create_netbox_tags(self.tags)

    def get_memory(self):
        mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")  # e.g. 4015976448
        mem_gib = mem_bytes / (1024.0**2)  # e.g. 3.74
        return int(mem_gib)

    def get_vcpus(self):
        return os.cpu_count()

    def get_netbox_vm(self):
        hostname = get_hostname(config)
        vm = nb.virtualization.virtual_machines.get(name=hostname)
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
        nb_tenant = nb.tenancy.tenants.get(slug=self.get_tenant())
        return nb_tenant

    def netbox_create_or_update(self, config):
        logging.debug("It's a virtual machine")
        created = False
        updated = 0

        hostname = get_hostname(config)
        vm = self.get_netbox_vm()

        vcpus = self.get_vcpus()
        memory = self.get_memory()
        tenant = self.get_netbox_tenant()
        if not vm:
            logging.debug("Creating Virtual machine..")
            cluster = self.get_netbox_cluster(config.virtual.cluster_name)

            vm = nb.virtualization.virtual_machines.create(
                name=hostname,
                cluster=cluster.id,
                platform=self.device_platform.id,
                vcpus=vcpus,
                memory=memory,
                tenant=tenant.id if tenant else None,
                tags=[{"name": x} for x in self.tags],
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

            vm_tags = sorted(set([x.name for x in vm.tags]))
            tags = sorted(set(self.tags))
            if vm_tags != tags:
                new_tags_ids = [x.id for x in self.nb_tags]
                if not config.preserve_tags:
                    vm.tags = new_tags_ids
                else:
                    vm_tags_ids = [x.id for x in vm.tags]
                    vm.tags = sorted(set(new_tags_ids + vm_tags_ids))
                updated += 1

            if vm.platform != self.device_platform:
                vm.platform = self.device_platform
                updated += 1

        if updated:
            vm.save()

    def print_debug(self):
        self.network = VirtualNetwork(server=self)
        print("Cluster:", self.get_netbox_cluster(config.virtual.cluster_name))
        print("Platform:", self.device_platform)
        print("VM:", self.get_netbox_vm())
        print("vCPU:", self.get_vcpus())
        print("Memory:", f"{self.get_memory()} MB")
        print(
            "NIC:",
        )
        pprint(self.network.get_network_cards())
        pass
