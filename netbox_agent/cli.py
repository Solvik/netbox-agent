import argparse

from netbox_agent.dell.dell import DellHost
import netbox_agent.dmidecode as dmidecode
from netbox_agent.hp.hp import HPHost

MANUFACTURERS = {
   'Dell Inc.': DellHost,
   'HP': HPHost,
   'HPE': HPHost,
   }


def run(args):
    manufacturer = dmidecode.get_by_type('Chassis')[0].get('Manufacturer')
    server = MANUFACTURERS[manufacturer](dmidecode)
    if args.debug:
        server.print_debug()
    if args.register:
        server.netbox_create()
    return True


def main():
    parser = argparse.ArgumentParser(description='Netbox agent command line')
    parser.add_argument('--register', action='store_true',
                        help='Register server in Netbox')
    parser.add_argument('--debug', action='store_true',
                        help='Print debug informations')

    args = parser.parse_args()
    return run(args)


if __name__ == '__main__':
    main()
