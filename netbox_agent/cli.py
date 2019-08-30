import argparse

from netbox_agent.logging import logging # NOQA
from netbox_agent.vendors.dell import DellHost
import netbox_agent.dmidecode as dmidecode
from netbox_agent.config import config
from netbox_agent.vendors.hp import HPHost
from netbox_agent.vendors.qct import QCTHost
from netbox_agent.vendors.supermicro import SupermicroHost

MANUFACTURERS = {
   'Dell Inc.': DellHost,
   'HP': HPHost,
   'HPE': HPHost,
   'Supermicro': SupermicroHost,
   'Quanta Cloud Technology Inc.': QCTHost,
   }


def run(config):
    manufacturer = dmidecode.get_by_type('Chassis')[0].get('Manufacturer')
    server = MANUFACTURERS[manufacturer](dmi=dmidecode)
    print(config.netbox.url)
    print(config.netbox.token)
    if config.debug:
        server.print_debug()
    if config.register:
        server.netbox_create()
    if config.update_all:
        server.netbox_update()
    return True


def main():
    return run(config)


if __name__ == '__main__':
    main()
