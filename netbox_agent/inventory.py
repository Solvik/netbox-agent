import logging
import subprocess
import re

from netbox_agent.config import netbox_instance as nb, config
from netbox_agent.misc import is_tool
from netbox_agent.raid.hp import HPRaid
from netbox_agent.raid.storcli import StorcliRaid
from netbox_agent.lshw import LSHW

from pprint import pprint

INVENTORY_TAG = {
    'cpu': {'name': 'hw:cpu', 'slug': 'hw-cpu'},
    'disk': {'name': 'hw:disk', 'slug': 'hw-disk'},
    'interface':{'name': 'hw:interface', 'slug':'hw-interface'},
    'memory': {'name': 'hw:memory', 'slug': 'hw-memory'},
    'motherboard':{'name': 'hw:motherboard', 'slug':'hw-motherboard'},
    'raid_card': {'name': 'hw:raid_card', 'slug': 'hw-raid-card'},
    }

for key, tag in INVENTORY_TAG.items():
    nb_tag = nb.extras.tags.get(
        name=tag['name']
        )
    if not nb_tag:
        nb_tag = nb.extras.tags.create(
            name=tag['name'],
            slug=tag['slug'],
            comments=tag['name'],
            )


class Inventory():
    """
    Better Inventory items coming, see:
    - https://github.com/netbox-community/netbox/issues/3087
    - https://github.com/netbox-community/netbox/issues/3333

    This class implements for:
    * memory
    * cpu
    * raid cards
    * disks

    methods that:
    * get local item
    * get netbox item
    * create netbox item
    * update netbox item

    Known issues:
    - no scan of non-raid devices
    - no scan of NVMe devices
    """

    def __init__(self, server):
        self.server = server
        self.device_id = self.server.get_netbox_server().id
        self.raid = None
        self.disks = []

        self.lshw = LSHW()

    def find_or_create_manufacturer(self, name):
        if name is None:
            return None

        manufacturer = nb.dcim.manufacturers.get(
            name=name,
        )

        """
           No spaces in the slug allowed.
        """
        if not manufacturer:
            logging.info('Creating missing manufacturer {name}'.format(name=name))
            manufacturer = nb.dcim.manufacturers.create(
                name=name,
                slug=name.replace(' ','-').lower(),
            )

            logging.info('Creating missing manufacturer {name}'.format(name=name))

        return manufacturer

    def get_netbox_inventory(self, device_id, tag):
        try:
            items = nb.dcim.inventory_items.filter(
                device_id=device_id,
                tag=tag
            )
        except:
            logging.info('Tag {tag} is missing, returning empty array.'.format(tag=tag))
            items = []

        return items

    def create_netbox_inventory_item(self, device_id, tags, vendor, name, serial, description):
        manufacturer = self.find_or_create_manufacturer(vendor)

        _ = nb.dcim.inventory_items.create(
            device=device_id,
            manufacturer = manufacturer.id,
            discovered=True,
            tags=tags,
            name='{}'.format(name),
            serial='{}'.format(serial),
            description=description
        )

        logging.info('Creating inventory item {} {}/{} {} '.format(vendor, name, serial, description))

    def get_hw_motherboards(self):
        motherboards = []
        
        m = {}
        m['serial'] = self.lshw.motherboard_serial
        m['vendor'] = self.lshw.vendor
        m['name'] = '{} {}'.format(self.lshw.vendor, self.lshw.motherboard)
        m['description'] = '{} Motherboard'.format(self.lshw.motherboard)

        motherboards.append(m)

        return motherboards

    def do_netbox_motherboard(self):

        motherboards = self.get_hw_motherboards()
        nb_motherboards = self.get_netbox_inventory(
                device_id=self.device_id,
                tag=INVENTORY_TAG['motherboard']['slug'])

        for nb_motherboard in nb_motherboards:
            if nb_motherboard.serial not in [x['serial'] for x in motherboards]:
                logging.info('Deleting unknown motherboard {vendor} {motherboard}/{serial}'.format(
                    motherboard=self.lshw.motherboard,
                    serial=nb_motherboard.serial,
                ))
                nb_motherboard.delete()

        # create interfaces that are not in netbox
        for motherboard in motherboards:
            if motherboard.get('serial') not in [x.serial for x in nb_motherboards]:
                self.create_netbox_inventory_item(
                    device_id = self.device_id,
                    tags=[INVENTORY_TAG['motherboard']['slug']],
                    vendor='{}'.format(motherboard.get('vendor', 'N/A')),
                    serial='{}'.format(motherboard.get('serial', '000000')),
                    name='{}'.format(motherboard.get('name')),
                    description='{}'.format(motherboard.get('description'))
                )

    def create_netbox_interface(self, iface):
        manufacturer = self.find_or_create_manufacturer(iface["vendor"])
        _ = nb.dcim.inventory_items.create(
            device=self.device_id,
            manufacturer = manufacturer.id,
            discovered=True,
            tags=[INVENTORY_TAG['interface']['name']],
            name="{}".format(iface['product']),
            serial='{}'.format(iface['serial']),
            description='{} {}'.format(iface['description'], iface['name'])
        )

    def do_netbox_interfaces(self):
        nb_interfaces = self.get_netbox_inventory(
                device_id=self.device_id,
                tag=INVENTORY_TAG['interface']['slug'])
        interfaces = self.lshw.interfaces

        # delete interfaces that are in netbox but not locally
        # use the serial_number has the comparison element
        for nb_interface in nb_interfaces:
            if nb_interface.serial not in [x['serial'] for x in interfaces]:
                logging.info('Deleting unknown interface {serial}'.format(
                    serial=nb_interface.serial,
                ))
                nb_interface.delete()

        # create interfaces that are not in netbox
        for iface in interfaces:
            if iface.get('serial') not in [x.serial for x in nb_interfaces]:
                self.create_netbox_interface(iface)
        
    def create_netbox_cpus(self):
        for cpu in self.lshw.get_hw_linux('cpu'):
            manufacturer = self.find_or_create_manufacturer(cpu["vendor"])
            _ = nb.dcim.inventory_items.create(
                device=self.device_id,
                manufacturer = manufacturer.id,
                discovered=True,
                tags=[INVENTORY_TAG['cpu']['name']],
                name=cpu['product'],
                description='CPU {}'.format(cpu['location']),
                # asset_tag=cpu['location']
            )

            logging.info('Creating CPU model {}'.format(cpu['product']))

    def do_netbox_cpus(self):
        cpus = self.lshw.get_hw_linux('cpu')
        nb_cpus = self.get_netbox_inventory(
            device_id=self.device_id,
            tag=INVENTORY_TAG['cpu']['slug'],
        )

        if not len(nb_cpus) or \
           len(nb_cpus) and len(cpus) != len(nb_cpus):
            for x in nb_cpus:
                x.delete()

        self.create_netbox_cpus()

    def get_raid_cards(self):
        if self.server.manufacturer == 'Dell':
            if is_tool('storcli'):
                self.raid = StorcliRaid()
        elif self.server.manufacturer == 'HP':
            if is_tool('ssacli'):
                self.raid = HPRaid()

        if not self.raid:
            return []

        controllers = self.raid.get_controllers()
        if len(self.raid.get_controllers()):
            return controllers

    def create_netbox_raid_card(self, raid_card):
        manufacturer = self.find_or_create_manufacturer(
            raid_card.get_manufacturer()
        )

        name = raid_card.get_product_name()
        serial = raid_card.get_serial_number()
        nb_raid_card = nb.dcim.inventory_items.create(
            device=self.device_id,
            discovered=True,
            manufacturer=manufacturer.id if manufacturer else None,
            tags=[INVENTORY_TAG['raid_card']['name']],
            name='{}'.format(name),
            serial='{}'.format(serial),
            description='RAID Card',
        )
        logging.info('Creating RAID Card {name} (SN: {serial})'.format(
            name=name,
            serial=serial,
        ))
        return nb_raid_card

    def create_netbox_raid_cards(self):
        for raid_card in self.get_netbox_inventory(
                device_id=self.device_id,
                tag=[INVENTORY_TAG['raid_card']['name']]
                ):
            self.create_netbox_raid_card(raid_card)

    def update_netbox_raid_cards(self):
        """
        Update raid cards in netbobx
        Since we only push:
        * Name
        * Manufacturer
        * Serial

        We only need to handle destroy and new cards
        """

        nb_raid_cards = self.self.get_netbox_inventory(
                device_id=self.device_id,
                tag=[INVENTORY_TAG['raid_card']['name']]
                )
        raid_cards = self.get_raid_cards()

        # delete cards that are in netbox but not locally
        # use the serial_number has the comparison element
        for nb_raid_card in nb_raid_cards:
            if nb_raid_card.serial not in [x.get_serial_number() for x in raid_cards]:
                logging.info('Deleting unknown locally RAID Card {serial}'.format(
                    serial=nb_raid_card.serial,
                ))
                nb_raid_card.delete()

        # create card that are not in netbox
        for raid_card in raid_cards:
            if raid_card.get_serial_number() not in [x.serial for x in nb_raid_cards]:
                self.create_netbox_raid_card(raid_card)

    def get_hw_disks(self):
        disks = []

        for disk in self.lshw.get_hw_linux("storage"):
            d = {}
            d["name"] = ""
            d['size'] = '{} GB'.format(int(disk['size']/1024/1024/1024))
            d['model'] = disk['product']
            d['logicalname'] = disk['logicalname']
            d['description'] = disk['description']
            d['serial'] = disk['serial']

            if 'vendor' in disk:
                d['vendor'] = disk['vendor']

            if disk['product'].startswith('ST'):
                d['vendor'] = 'Seagate'

            if disk['product'].startswith('Crucial'):
                d['vendor'] = 'Crucial'

            if disk['product'].startswith('Micron'):
                d['vendor'] = 'Micron'

            if disk['product'].startswith('INTEL'):
                d['vendor'] = 'Intel'

            if disk['product'].startswith('Samsung'):
                d['vendor'] = 'Samsung'

            disks.append(d)

        for raid_card in self.get_raid_cards():
            disks += raid_card.get_physical_disks()

        return disks

    def create_netbox_disk(self, disk):
            if "vendor" in disk:
                manufacturer = self.find_or_create_manufacturer(disk["vendor"])

            _ = nb.dcim.inventory_items.create(
                device=self.device_id,
                discovered=True,
                tags=[INVENTORY_TAG['disk']['name']],
                name='{} - {} ({})'.format(
                    disk.get('description', 'Unknown'),
                    disk.get('logicalname', 'Unknown'), 
                    disk.get('size', 0)
                ),
                serial=disk['serial'],
                part_id=disk['model'],
                description='Device {}'.format(disk.get('logicalname', 'Unknown')),
                manufacturer=manufacturer.id
            )

            logging.info('Creating Disk {model} {serial}'.format(
                model=disk['model'],
                serial=disk['serial'],
            ))

    def do_netbox_disks(self):
        nb_disks = self.get_netbox_inventory(
                device_id=self.device_id,
                tag=INVENTORY_TAG['disk']['slug'])
        disks = self.get_hw_disks()

        # delete disks that are in netbox but not locally
        # use the serial_number has the comparison element
        for nb_disk in nb_disks:
            if nb_disk.serial not in [x['serial'] for x in disks]:
                logging.info('Deleting unknown locally Disk {serial}'.format(
                    serial=nb_disk.serial,
                ))
                nb_disk.delete()

        # create disks that are not in netbox
        for disk in disks:
            if disk.get('serial') not in [x.serial for x in nb_disks]:
                self.create_netbox_disk(disk)

    def create_netbox_memory(self, memory):
        manufacturer = self.find_or_create_manufacturer(memory['vendor'])

        nb_memory = nb.dcim.inventory_items.create(
            device=self.device_id,
            discovered=True,
            manufacturer=manufacturer.id,
            tags=[INVENTORY_TAG['memory']['name']],
            name='{} ({}GB)'.format(memory['description'], memory['size']),
            part_id=memory['product'],
            serial=memory['serial'],
            description='Slot {}'.format(memory['slot']),
        )

        logging.info('Creating Memory {location} {type} {size}GB'.format(
            location=memory['slot'],
            type=memory['product'],
            size=memory['size'],
        ))

        return nb_memory

    def do_netbox_memories(self):
        memories = self.lshw.memories
        nb_memories = self.get_netbox_inventory(
                device_id=self.device_id,
                tag=INVENTORY_TAG['memory']['slug']
                )

        for nb_memory in nb_memories:
            if nb_memory.serial not in [x['serial'] for x in memories]:
                logging.info('Deleting unknown locally Memory {serial}'.format(
                    serial=nb_memory.serial,
                ))
                nb_memory.delete()

        for memory in memories:
            if memory.get('serial') not in [x.serial for x in nb_memories]:
                self.create_netbox_memory(memory)

    def create(self):
        if config.inventory is None:
            return False
        self.do_netbox_cpus()
        self.do_netbox_memories()
        self.create_netbox_raid_cards()
        self.do_netbox_disks()
        self.do_netbox_interfaces()
        self.do_netbox_motherboard()
        return True

    def update(self):
        if config.inventory is None or config.update_inventory is None:
            return False
        self.do_netbox_cpus()
        self.do_netbox_memories()
        self.update_netbox_raid_cards()
        self.do_netbox_disks()
        self.do_netbox_interfaces()
        self.do_netbox_motherboard()
        return True
