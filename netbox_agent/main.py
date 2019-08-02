from netbox_agent.dmidecode import Dmidecode
from netbox_agent.dell.dell import DellHost
from netbox_agent.hp.hp import HPHost

MANUFACTURERS = {
   'Dell Inc.': DellHost,
   'HP': HPHost,
   'HPE': HPHost,    
   }

def main():
    dmi = Dmidecode()
    manufacturer = dmi.get('chassis')[0].get('Manufacturer')
    server = MANUFACTURERS[manufacturer](dmi)
    print(server.get_chassis())
    print(server.get_service_tag())
    print(server.get_chassis_service_tag())
    server.netbox_create()
    print(server.get_network_cards())

if __name__ == '__main__':
    main()
