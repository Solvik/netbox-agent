import logging
import re

import pynetbox

from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.lshw import LSHW
from netbox_agent.misc import get_vendor, is_tool
from netbox_agent.raid.hp import HPRaid
from netbox_agent.raid.omreport import OmreportRaid
from netbox_agent.raid.storcli import StorcliRaid

INVENTORY_TAG = {
    'cpu': {'name': 'hw:cpu', 'slug': 'hw-cpu'},
    'disk': {'name': 'hw:disk', 'slug': 'hw-disk'},
    'interface': {'name': 'hw:interface', 'slug': 'hw-interface'},
    'memory': {'name': 'hw:memory', 'slug': 'hw-memory'},
    'motherboard': {'name': 'hw:motherboard', 'slug': 'hw-motherboard'},
    'raid_card': {'name': 'hw:raid_card', 'slug': 'hw-raid-card'},
}


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
        self.create_netbox_tags()
        self.server = server
        netbox_server = self.server.get_netbox_server()

        self.device_id = netbox_server.id if netbox_server else None
        self.raid = None
        self.disks = []

        self.lshw = LSHW()

    def create_netbox_tags(self):
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

    def find_or_create_manufacturer(self, name):
        if name is None:
            return None

        manufacturer = nb.dcim.manufacturers.get(
            name=name,
        )
        if not manufacturer:
            logging.info('Creating missing manufacturer {name}'.format(name=name))
            manufacturer = nb.dcim.manufacturers.create(
                name=name,
                slug=re.sub('[^A-Za-z0-9]+', '-', name).lower(),
            )

            logging.info('Creating missing manufacturer {name}'.format(name=name))

        return manufacturer

    def get_netbox_inventory(self, device_id, tag):
        try:
            items = nb.dcim.inventory_items.filter(
                device_id=device_id,
                tag=tag
            )
        except pynetbox.core.query.RequestError:
            logging.info('Tag {tag} is missing, returning empty array.'.format(tag=tag))
            items = []

        return items

    def create_netbox_inventory_item(self, device_id, tags, vendor, name, serial, description):
        manufacturer = self.find_or_create_manufacturer(vendor)

        _ = nb.dcim.inventory_items.create(
            device=device_id,
            manufacturer=manufacturer.id,
            discovered=True,
            tags=tags,
            name='{}'.format(name),
            serial='{}'.format(serial),
            description=description
        )

        logging.info('Creating inventory item {} {}/{} {} '.format(
            vendor,
            name,
            serial,
            description)
        )

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
                logging.info('Deleting unknown motherboard {motherboard}/{serial}'.format(
                    motherboard=self.lshw.motherboard,
                    serial=nb_motherboard.serial,
                ))
                nb_motherboard.delete()

        # create interfaces that are not in netbox
        for motherboard in motherboards:
            if motherboard.get('serial') not in [x.serial for x in nb_motherboards]:
                self.create_netbox_inventory_item(
                    device_id=self.device_id,
                    tags=[INVENTORY_TAG['motherboard']['name']],
                    vendor='{}'.format(motherboard.get('vendor', 'N/A')),
                    serial='{}'.format(motherboard.get('serial', 'No SN')),
                    name='{}'.format(motherboard.get('name')),
                    description='{}'.format(motherboard.get('description'))
                )

    def create_netbox_interface(self, iface):
        manufacturer = self.find_or_create_manufacturer(iface["vendor"])
        _ = nb.dcim.inventory_items.create(
            device=self.device_id,
            manufacturer=manufacturer.id,
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
                manufacturer=manufacturer.id,
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
        raid_class = None
        if self.server.manufacturer == 'Dell':
            if is_tool('omreport'):
                raid_class = OmreportRaid
            if is_tool('storcli'):
                raid_class = StorcliRaid
        elif self.server.manufacturer == 'HP':
            if is_tool('ssacli'):
                raid_class = HPRaid

        if not raid_class:
            return []

        self.raid = raid_class()
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

    def do_netbox_raid_cards(self):
        """
        Update raid cards in netbobx
        Since we only push:
        * Name
        * Manufacturer
        * Serial

        We only need to handle destroy and new cards
        """

        nb_raid_cards = self.get_netbox_inventory(
            device_id=self.device_id,
            tag=[INVENTORY_TAG['raid_card']['slug']]
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

    def is_virtual_disk(self, disk):
        logicalname = disk.get('logicalname')
        description = disk.get('description')
        size = disk.get('size')
        product = disk.get('product')

        non_raid_disks = [
            'MR9361-8i',
        ]

        if size is None and logicalname is None or \
           'virtual' in product.lower() or 'logical' in product.lower() or \
           product in non_raid_disks or \
           description == 'SCSI Enclosure' or \
           'volume' in description.lower():
            return True
        return False

    def get_hw_disks(self):
        disks = []

        for disk in self.lshw.get_hw_linux("storage"):
            if self.is_virtual_disk(disk):
                continue

            logicalname = disk.get('logicalname')
            description = disk.get('description')
            size = disk.get('size', 0)
            product = disk.get('product')
            serial = disk.get('serial')

            d = {}
            d["name"] = ""
            d['Size'] = '{} GB'.format(int(size / 1024 / 1024 / 1024))
            d['logicalname'] = logicalname
            d['description'] = description
            d['SN'] = serial
            d['Model'] = product
            if disk.get('vendor'):
                d['Vendor'] = disk['vendor']
            else:
                d['Vendor'] = get_vendor(disk['product'])
            disks.append(d)

        for raid_card in self.get_raid_cards():
            disks += raid_card.get_physical_disks()

        # remove duplicate serials
        seen = set()
        uniq = [x for x in disks if x['SN'] not in seen and not seen.add(x['SN'])]
        return uniq

    def create_netbox_disk(self, disk):
        manufacturer = None
        if "Vendor" in disk:
            manufacturer = self.find_or_create_manufacturer(disk["Vendor"])

        logicalname = disk.get('logicalname')
        desc = disk.get('description')
        # nonraid disk
        if logicalname and desc:
            if type(logicalname) is list:
                logicalname = logicalname[0]
            name = '{} - {} ({})'.format(
                desc,
                logicalname,
                disk.get('Size', 0))
            description = 'Device {}'.format(disk.get('logicalname', 'Unknown'))
        else:
            name = '{} ({})'.format(disk['Model'], disk['Size'])
            description = '{}'.format(disk['Type'])

        _ = nb.dcim.inventory_items.create(
            device=self.device_id,
            discovered=True,
            tags=[INVENTORY_TAG['disk']['name']],
            name=name,
            serial=disk['SN'],
            part_id=disk['Model'],
            description=description,
            manufacturer=manufacturer.id if manufacturer else None
        )

        logging.info('Creating Disk {model} {serial}'.format(
            model=disk['Model'],
            serial=disk['SN'],
        ))

    def do_netbox_disks(self):
        nb_disks = self.get_netbox_inventory(
            device_id=self.device_id,
            tag=INVENTORY_TAG['disk']['slug'])
        disks = self.get_hw_disks()

        # delete disks that are in netbox but not locally
        # use the serial_number has the comparison element
        for nb_disk in nb_disks:
            if nb_disk.serial not in [x['SN'] for x in disks if x.get('SN')]:
                logging.info('Deleting unknown locally Disk {serial}'.format(
                    serial=nb_disk.serial,
                ))
                nb_disk.delete()

        # create disks that are not in netbox
        for disk in disks:
            if disk.get('SN') not in [x.serial for x in nb_disks]:
                self.create_netbox_disk(disk)

    def create_netbox_memory(self, memory):
        manufacturer = self.find_or_create_manufacturer(memory['vendor'])
        name = 'Slot {} ({}GB)'.format(memory['slot'], memory['size'])
        nb_memory = nb.dcim.inventory_items.create(
            device=self.device_id,
            discovered=True,
            manufacturer=manufacturer.id,
            tags=[INVENTORY_TAG['memory']['name']],
            name=name,
            part_id=memory['product'],
            serial=memory['serial'],
            description=memory['description'],
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

    def create_or_update(self):
        if config.inventory is None or config.update_inventory is None:
            return False
        self.do_netbox_cpus()
        self.do_netbox_memories()
        self.do_netbox_raid_cards()
        self.do_netbox_disks()
        self.do_netbox_interfaces()
        self.do_netbox_motherboard()
        return True
