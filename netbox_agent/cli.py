import sys
from packaging import version
import netbox_agent.dmidecode as dmidecode
from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.logging import logging  # NOQA
from netbox_agent.vendors.dell import DellHost
from netbox_agent.vendors.generic import GenericHost
from netbox_agent.vendors.hp import HPHost
from netbox_agent.vendors.qct import QCTHost
from netbox_agent.vendors.supermicro import SupermicroHost
from netbox_agent.virtualmachine import VirtualMachine, is_vm

MANUFACTURERS = {
    "Dell Inc.": DellHost,
    "HP": HPHost,
    "HPE": HPHost,
    "Supermicro": SupermicroHost,
    "Quanta Cloud Technology Inc.": QCTHost,
    "Generic": GenericHost,
}


def run(config):
    dmi = dmidecode.parse()

    if config.virtual.enabled or is_vm(dmi):
        if config.virtual.hypervisor:
            raise Exception("This host can't be a hypervisor because it's a VM")
        if not config.virtual.cluster_name:
            raise Exception("virtual.cluster_name parameter is mandatory because it's a VM")
        server = VirtualMachine(dmi=dmi)
    else:
        if config.virtual.hypervisor and not config.virtual.cluster_name:
            raise Exception(
                "virtual.cluster_name parameter is mandatory because it's a hypervisor"
            )
        manufacturer = dmidecode.get_by_type(dmi, "Chassis")[0].get("Manufacturer")
        try:
            server = MANUFACTURERS[manufacturer](dmi=dmi)
        except KeyError:
            server = GenericHost(dmi=dmi)

    if version.parse(nb.version) < version.parse("3.7"):
        print("netbox-agent is not compatible with Netbox prior to version 3.7")
        return False

    if (
        config.register
        or config.update_all
        or config.update_network
        or config.update_location
        or config.update_inventory
        or config.update_psu
    ):
        server.netbox_create_or_update(config)
    if config.debug:
        server.print_debug()
    return True


def main():
    return run(config)


if __name__ == "__main__":
    sys.exit(main())
