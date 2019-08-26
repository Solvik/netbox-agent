import argparse

from netbox_agent.vendors.dell import DellHost
import netbox_agent.dmidecode as dmidecode
from netbox_agent.vendors.hp import HPHost
from netbox_agent.vendors.qct import QCTHost
from netbox_agent.vendors.supermicro import SupermicroHost
from netbox_agent.logging import logging # NOQA

MANUFACTURERS = {
   'Dell Inc.': DellHost,
   'HP': HPHost,
   'HPE': HPHost,
   'Supermicro': SupermicroHost,
   'Quanta Cloud Technology Inc.': QCTHost,
   }


def run(args):
    manufacturer = dmidecode.get_by_type('Chassis')[0].get('Manufacturer')
    server = MANUFACTURERS[manufacturer](dmi=dmidecode)
    if args.debug:
        server.print_debug()
    if args.register:
        server.netbox_create()
    if args.update:
        server.netbox_update()
    return True


def main():
    parser = argparse.ArgumentParser(description='Netbox agent command line')
    parser.add_argument('-r', '--register', action='store_true',
                        help='Register server in Netbox')
    parser.add_argument('-u', '--update', action='store_true',
                        help='Update server in Netbox')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Print debug informations')

    args = parser.parse_args()
    return run(args)


if __name__ == '__main__':
    main()
