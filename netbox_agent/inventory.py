import subprocess
import re
from shutil import which

from netbox_agent.config import netbox_instance as nb
from netbox_agent.raid.hp import HPRaid
from netbox_agent.raid.dell import StorcliRaid
import netbox_agent.dmidecode as dmidecode

INVENTORY_TAG = {
    'cpu': {'name': 'hw:cpu', 'slug': 'hw-cpu'},
    'memory': {'name': 'hw:memory', 'slug': 'hw-memory'},
    'disk': {'name': 'hw:disk', 'slug': 'hw-disk'},
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


def is_tool(name):
    '''Check whether `name` is on PATH and marked as executable.'''
    return which(name) is not None
        
class DictDiffer(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current, self.set_past = set(current_dict.keys()), set(past_dict.keys())
        self.intersect = self.set_current.intersection(self.set_past)
        
    def added(self):
        return self.set_current - self.intersect
    def removed(self):
        return self.set_past - self.intersect
    def changed(self):
        return set(o for o in self.intersect if self.past_dict[o] != self.current_dict[o])
    def unchanged(self):
        return set(o for o in self.intersect if self.past_dict[o] == self.current_dict[o])

class Inventory():
    """
    Better Inventory items coming, see:
    - https://github.com/netbox-community/netbox/issues/3087
    - https://github.com/netbox-community/netbox/issues/3333
    """

    def __init__(self, server):
        self.server = server
        self.device_id = self.server.get_netbox_server().id
        self.raid = None
        self.disks = []
        self.memories = []

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
            cpu = nb.dcim.inventory_items.create(
                device=self.device_id,
                tags=[INVENTORY_TAG['cpu']['name']],
                name=model,
                discovered=True,
            )

    def get_raid_cards(self):
        if self.server.manufacturer == 'Dell':
            if is_tool('storcli'):
                self.raid = StorcliRaid()
        elif self.server.manufacturer == 'HP':
            if is_tool('ssacli'):
                self.raid = HPRaid()

        if not self.raid:
            return

        controllers = self.raid.get_controllers()
        if len(self.raid.get_controllers()):
            return self.raid.get_controllers()
        
    def get_netbox_raid_cards(self):
        raid_cards = nb.dcim.inventory_items.filter(
            device_id=self.device_id,
            tag=INVENTORY_TAG['raid_card']['slug'],
            )
        return raid_cards

    def find_or_create_manufacturer(self, name):
        if name is None:
            return none
        manufacturer = nb.dcim.manufacturers.get(
            name=name,
        )
        if not manufacturer:
            manufacturer = nb.dcim.manufacturers.create(
                name=name,
                slug=name.lower(),
            )
        return manufacturer

    def create_netbox_raid_card(self, raid_card):
        manufacturer = self.find_or_create_manufacturer(
            raid_card.get_manufacturer()
        )
        nb_raid_card = nb.dcim.inventory_items.create(
            device=self.device_id,
            discovered=True,
            manufacturer=manufacturer.id,
            tags=[INVENTORY_TAG['raid_card']['name']],
            name='{}'.format(raid_card.get_product_name()),
            serial='{}'.format(raid_card.get_serial_number()),
        )
        
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
                nb_raid_card.delete()

        # create card that are not in netbox
        for raid_card in raid_cards:
            if raid_card.get_serial_number() not in [x.serial for x in nb_raid_cards]:
                self.create_netbox_raid_card(raid_card)

    def get_disks(self):
        pass

    def get_netbox_disks(self):
        pass

    def create_netbox_disks(self):
        pass

    def update_netbox_disks(self):
        pass

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

    def create_netbox_memory(self):
        for memory in self.get_memory():
            manufacturer = nb.dcim.manufacturers.get(
                name=memory['Manufacturer']
            )
            if not manufacturer:
                manufacturer = nb.dcim.manufacturers.create(
                    name=memory['Manufacturer'],
                    slug=memory['Manufacturer'].lower(),
                    )
            memories = nb.dcim.inventory_items.create(
                device=self.device_id,
                discovered=True,
                manufacturer=manufacturer.id,
                tags=[INVENTORY_TAG['memory']['name']],
                name='{} ({})'.format(memory['Locator'], memory['Size']),
                part_id=memory['PN'],
                serial=memory['SN'],
            )

    def update_netbox_memory(self):
        pass

    def create(self):
        self.create_netbox_cpus()
        self.create_netbox_memory()
        self.create_netbox_raid_cards()

    def update(self):
        # assume we don't update CPU?
        self.update_netbox_memory()
        self.update_netbox_raid_cards()
