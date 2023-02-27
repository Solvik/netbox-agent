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
    'Dell Inc.': DellHost,
    'HP': HPHost,
    'HPE': HPHost,
    'Supermicro': SupermicroHost,
    'Quanta Cloud Technology Inc.': QCTHost,
    'Generic': GenericHost,
    'Virtual Machine': VirtualMachine,
}


def main():
    dmi = dmidecode.parse()

    if version.parse(nb.version) < version.parse('2.9'):
        raise SystemExit('netbox-agent requires Netbox version 2.9 or higher')

    if is_vm(dmi):
        if not config.virtual.cluster_name:
            raise SystemExit(
                'The `virtual.cluster_name` parameter/configuration value must'
                'be set for virtualized systems.'
            )
        kind = 'Virtual'
    else:
        chassis = dmidecode.get_by_type(dmi, 'Chassis')
        kind = chassis[0].get('Manufacturer')

    server_class = MANUFACTURERS.get(kind, GenericHost)
    server = server_class(dmi)

    if (
        config.register or
        config.update_all or
        config.update_network or
        config.update_location or
        config.update_inventory or
        config.update_psu
    ):
        server.netbox_create_or_update(config)

    if config.debug:
        server.print_debug()


if __name__ == '__main__':
    main()
