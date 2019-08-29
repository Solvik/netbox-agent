import logging
import subprocess
import re

from netbox_agent.config import netbox_instance as nb, INVENTORY_ENABLED
from netbox_agent.misc import is_tool
from netbox_agent.raid.hp import HPRaid
from netbox_agent.raid.storcli import StorcliRaid
from netbox_agent.lshw import LSHW

INVENTORY_TAG = {
    'cpu': {'name': 'hw:cpu', 'slug': 'hw-cpu'},
    'disk': {'name': 'hw:disk', 'slug': 'hw-disk'},
    'memory': {'name': 'hw:memory', 'slug': 'hw-memory'},
    'network':{'name': 'hw:network', 'slug':'hw-network'},
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

    def get_cpus(self):
        model = None
        nb = None

        output = subprocess.getoutput('lscpu')
        model_re = re.search(r'Model name: (.*)', output)
        if len(model_re.groups()) > 0:
            model = model_re.groups()[0].strip()
        socket_re = re.search(r'Socket\(s\): (.*)', output)
        if len(socket_re.groups()) > 0:
            nb = int(socket_re.groups()[0].strip())
        return nb, model

    def create_netbox_cpus(self):
        nb_cpus, model = self.get_cpus()
        for i in range(nb_cpus):
            _ = nb.dcim.inventory_items.create(
                device=self.device_id,
                tags=[INVENTORY_TAG['cpu']['name']],
                name=model,
                discovered=True,
                description='CPU',
            )
            logging.info('Creating CPU model {model}'.format(model=model))

    def update_netbox_cpus(self):
        cpus_number, model = self.get_cpus()
        nb_cpus = nb.dcim.inventory_items.filter(
            device_id=self.device_id,
            tag=INVENTORY_TAG['cpu']['slug'],
        )

        if not len(nb_cpus) or \
           len(nb_cpus) and cpus_number != len(nb_cpus):
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

    def get_netbox_raid_cards(self):
        raid_cards = nb.dcim.inventory_items.filter(
            device_id=self.device_id,
            tag=INVENTORY_TAG['raid_card']['slug'],
            )
        return raid_cards

    def find_or_create_manufacturer(self, name):
        if name is None:
            return None
        manufacturer = nb.dcim.manufacturers.get(
            name=name,
        )
        if not manufacturer:
            manufacturer = nb.dcim.manufacturers.create(
                name=name,
                slug=name.lower(),
            )
            logging.info('Creating missing manufacturer {name}'.format(name=name))
        return manufacturer

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
        for raid_card in self.get_raid_cards():
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

        nb_raid_cards = self.get_netbox_raid_cards()
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

    def get_disks(self):
        ret = []
        for raid_card in self.get_raid_cards():
            ret += raid_card.get_physical_disks()
        return ret

    def get_netbox_disks(self):
        disks = nb.dcim.inventory_items.filter(
            device_id=self.device_id,
            tag=INVENTORY_TAG['disk']['slug'],
            )
        return disks

    def create_netbox_disks(self):
        for disk in self.get_disks():
            _ = nb.dcim.inventory_items.create(
                device=self.device_id,
                discovered=True,
                tags=[INVENTORY_TAG['disk']['name']],
                name='{} ({})'.format(disk['Model'], disk['Size']),
                serial=disk['SN'],
            )
            logging.info('Creating Disk {model} {serial}'.format(
                model=disk['Model'],
                serial=disk['SN'],
            ))

    def update_netbox_disks(self):
        nb_disks = self.get_netbox_disks()
        disks = self.get_disks()

        # delete disks that are in netbox but not locally
        # use the serial_number has the comparison element
        for nb_disk in nb_disks:
            if nb_disk.serial not in [x['SN'] for x in disks]:
                logging.info('Deleting unknown locally Disk {serial}'.format(
                    serial=nb_disk.serial,
                ))
                nb_disk.delete()

        # create disks that are not in netbox
        for disk in disks:
            if disk['SN'] not in [x.serial for x in nb_disks]:
                nb_disk = nb.dcim.inventory_items.create(
                    device=self.device_id,
                    discovered=True,
                    tags=[INVENTORY_TAG['disk']['name']],
                    name='{} ({})'.format(disk['Model'], disk['Size']),
                    serial=disk['SN'],
                    description=disk.get('Type', ''),
                )
                logging.info('Creating Disk {model} {serial}'.format(
                    model=disk['Model'],
                    serial=disk['SN'],
                ))

    def get_memory(self):
        memories = []
        for _, value in self.server.dmi.parse().items():
            if value['DMIName'] == 'Memory Device' and \
               value['Size'] != 'No Module Installed':
                memories.append({
                    'Manufacturer': value['Manufacturer'].strip(),
                    'Size': value['Size'].strip(),
                    'PN': value['Part Number'].strip(),
                    'SN': value['Serial Number'].strip(),
                    'Locator': value['Locator'].strip(),
                    'Type': value['Type'].strip(),
                    })
        return memories

    def get_memory_total_size(self):
        total_size = 0
        for memory in self.get_memory():
            total_size += int(memory['Size'].split()[0])
        return total_size

    def get_netbox_memory(self):
        memories = nb.dcim.inventory_items.filter(
            device_id=self.device_id,
            tag=INVENTORY_TAG['memory']['slug'],
            )
        return memories

    def create_netbox_memory(self, memory):
        manufacturer = nb.dcim.manufacturers.get(
            name=memory['Manufacturer']
        )
        if not manufacturer:
            manufacturer = nb.dcim.manufacturers.create(
                name=memory['Manufacturer'],
                slug=memory['Manufacturer'].lower(),
            )
        nb_memory = nb.dcim.inventory_items.create(
            device=self.device_id,
            discovered=True,
            manufacturer=manufacturer.id,
            tags=[INVENTORY_TAG['memory']['name']],
            name='{} ({} {})'.format(memory['Locator'], memory['Size'], memory['Type']),
            part_id=memory['PN'],
            serial=memory['SN'],
            description='RAM',
        )
        logging.info('Creating Memory {type} {size}'.format(
            type=memory['Type'],
            size=memory['Size'],
        ))
        return nb_memory

    def create_netbox_memories(self):
        for memory in self.get_memory():
            self.create_netbox_memory(memory)

    def update_netbox_memory(self):
        memories = self.get_memory()
        nb_memories = self.get_netbox_memory()

        for nb_memory in nb_memories:
            if nb_memory.serial not in [x['SN'] for x in memories]:
                logging.info('Deleting unknown locally Memory {serial}'.format(
                    serial=nb_memory.serial,
                ))
                nb_memory.delete()
        for memory in memories:
            if memory['SN'] not in [x.serial for x in nb_memories]:
                self.create_netbox_memory(memory)

    def create(self):
        if not INVENTORY_ENABLED:
            return False
        self.create_netbox_cpus()
        self.create_netbox_memories()
        self.create_netbox_raid_cards()
        self.create_netbox_disks()
        return True

    def update(self):
        if not INVENTORY_ENABLED:
            return False
        self.update_netbox_cpus()
        self.update_netbox_memories()
        self.update_netbox_raid_cards()
        self.update_netbox_disks()
        return True
