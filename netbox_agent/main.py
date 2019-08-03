import sys
from pprint import pprint
import netbox_agent.dmidecode as dmidecode
from netbox_agent.dell.dell import DellHost
from netbox_agent.hp.hp import HPHost

MANUFACTURERS = {
   'Dell Inc.': DellHost,
   'HP': HPHost,
   'HPE': HPHost,    
   }

def main():
    manufacturer = dmidecode.get_by_type('Chassis')[0].get('Manufacturer')
    print(manufacturer)
    server = MANUFACTURERS[manufacturer](dmidecode)
    print(server.get_product_name())
    print(server.get_chassis())
    print(server.get_service_tag())
    print(server.get_chassis_service_tag())
    server.netbox_create()
#    print(server.get_network_cards())

if __name__ == '__main__':
    main()
