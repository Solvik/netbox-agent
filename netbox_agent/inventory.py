from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.lshw import LSHW
from netbox_agent.misc import get_vendor, is_tool
from netbox_agent.raid.hp import HPRaid
from netbox_agent.raid.omreport import OmreportRaid
from netbox_agent.raid.storcli import StorcliRaid
import traceback
import pynetbox
import logging
import json
import re


INVENTORY_TAG = {
    'cpu': {'name': 'hw:cpu', 'slug': 'hw-cpu'},
    'gpu': {'name': 'hw:gpu', 'slug': 'hw-gpu'},
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
    * gpus

    methods that:
    * get local item
    * get netbox item
    * create netbox item
    * update netbox item

    Known issues:
    - no scan of non-raid devices
    - no scan of NVMe devices
    """

    def __init__(self, server, update_expansion=False):
        self.create_netbox_tags()
        self.server = server
        self.update_expansion = update_expansion
        netbox_server = self.server.get_netbox_server(update_expansion)

        self.device_id = netbox_server.id if netbox_server else None
        self.raid = None
        self.disks = []

        self.lshw = LSHW()

    def create_netbox_tags(self):
        ret = []
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
            ret.append(nb_tag)
        return ret

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

        return list(items)

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
                    tags=[{'name': INVENTORY_TAG['motherboard']['name']}],
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
            tags=[{'name': INVENTORY_TAG['interface']['name']}],
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
                tags=[{'name': INVENTORY_TAG['cpu']['name']}],
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

    def get_raid_cards(self, filter_cards=False):
        raid_class = None
        if self.server.manufacturer in ('Dell', 'Huawei'):
            if is_tool('omreport'):
                raid_class = OmreportRaid
            if is_tool('storcli'):
                raid_class = StorcliRaid
        elif self.server.manufacturer in ('HP', 'HPE'):
            if is_tool('ssacli'):
                raid_class = HPRaid

        if not raid_class:
            return []

        self.raid = raid_class()

        if filter_cards and config.expansion_as_device \
                and self.server.own_expansion_slot():
            return [
                c for c in self.raid.get_controllers()
                if c.is_external() is self.update_expansion
            ]
        else:
            return self.raid.get_controllers()

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
            tags=[{'name': INVENTORY_TAG['raid_card']['name']}],
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
        raid_cards = self.get_raid_cards(filter_cards=True)

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

    def is_virtual_disk(self, disk, raid_devices):
        disk_type = disk.get('type')
        logicalname = disk.get('logicalname')
        description = disk.get('description')
        size = disk.get('size')
        product = disk.get('product')
        if logicalname in raid_devices or disk_type is None or product is None or description is None:
            return True
        non_raid_disks = [
            'MR9361-8i',
        ]

        if logicalname in raid_devices or \
           product in non_raid_disks or \
           'virtual' in product.lower() or \
           'logical' in product.lower() or \
           'volume' in description.lower() or \
           'dvd-ram' in description.lower() or \
           description == 'SCSI Enclosure' or \
           (size is None and logicalname is None):
            return True
        return False

    def get_hw_disks(self):
        disks = []

        for raid_card in self.get_raid_cards(filter_cards=True):
            disks.extend(raid_card.get_physical_disks())

        raid_devices = [
            d.get('custom_fields', {}).get('vd_device')
            for d in disks
            if d.get('custom_fields', {}).get('vd_device')
        ]

        for disk in self.lshw.get_hw_linux("storage"):
            if self.is_virtual_disk(disk, raid_devices):
                continue
            size = disk['size'] / 1073741824
            size_unit = 'GB'
            if size > 1024:
                size = size / 1024
                size_unit = 'TB'
            size_with_unit = '{0:.0f}{1}'.format(size, size_unit)
            d = {
                "name": 'NVMe {} ({})'.format(disk.get('product'), size_with_unit),
                'Size': size_with_unit,
                'logicalname': disk.get('logicalname'),
                'description': disk.get('description'),
                'SN': disk.get('serial'),
                'Model': disk.get('product'),
                'Type': disk.get('type'),
            }
            if disk.get('vendor'):
                d['Vendor'] = disk['vendor']
            else:
                d['Vendor'] = get_vendor(disk['product'])
            disks.append(d)

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
        name = '{} ({})'.format(disk['Model'], disk['Size'])
        description = disk['Type']
        sn = disk.get('SN', 'unknown')

        parms = {
            'device': self.device_id,
            'discovered': True,
            'tags': [{'name': INVENTORY_TAG['disk']['name']}],
            'name': name,
            'serial': sn,
            'part_id': disk['Model'],
            'description': description,
            'manufacturer': getattr(manufacturer, "id", None),
        }
        if config.process_virtual_drives:
            parms['custom_fields'] = disk.get("custom_fields", {})

        _ = nb.dcim.inventory_items.create(**parms)

        logging.info('Creating Disk {model} {serial}'.format(
            model=disk['Model'],
            serial=sn,
        ))

    def dump_disks_map(self, disks):
        disk_map = [d['custom_fields'] for d in disks if 'custom_fields' in d]
        if config.dump_disks_map == "-":
            f = sys.stdout
        else:
            f = open(config.dump_disks_map, "w")
        f.write(
            json.dumps(
                disk_map,
                separators=(',', ':'),
                indent=4,
                sort_keys=True
            )
        )
        if config.dump_disks_map != "-":
            f.close()

    def do_netbox_disks(self):
        nb_disks = self.get_netbox_inventory(
            device_id=self.device_id,
            tag=INVENTORY_TAG['disk']['slug']
        )
        disks = self.get_hw_disks()
        if config.dump_disks_map:
            try:
                self.dump_disks_map(disks)
            except Exception as e:
                logging.error("Failed to dump disks map: {}".format(e))
                logging.debug(traceback.format_exc())
        disk_serials = [d['SN'] for d in disks if 'SN' in d]

        # delete disks that are in netbox but not locally
        # use the serial_number has the comparison element
        for nb_disk in nb_disks:
            if nb_disk.serial not in disk_serials or \
                    config.force_disk_refresh:
                logging.info('Deleting unknown locally Disk {serial}'.format(
                    serial=nb_disk.serial,
                ))
                nb_disk.delete()

        if config.force_disk_refresh:
            nb_disks = self.get_netbox_inventory(
                device_id=self.device_id,
                tag=INVENTORY_TAG['disk']['slug']
            )

        # create disks that are not in netbox
        for disk in disks:
            if disk.get('SN') not in [d.serial for d in nb_disks]:
                self.create_netbox_disk(disk)

    def create_netbox_memory(self, memory):
        manufacturer = self.find_or_create_manufacturer(memory['vendor'])
        name = 'Slot {} ({}GB)'.format(memory['slot'], memory['size'])
        nb_memory = nb.dcim.inventory_items.create(
            device=self.device_id,
            discovered=True,
            manufacturer=manufacturer.id,
            tags=[{'name': INVENTORY_TAG['memory']['name']}],
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

    def create_netbox_gpus(self, gpus):
        for gpu in gpus:
            if 'product' in gpu and len(gpu['product']) > 50:
                gpu['product'] = (gpu['product'][:48] + '..')

            manufacturer = self.find_or_create_manufacturer(gpu["vendor"])
            _ = nb.dcim.inventory_items.create(
                device=self.device_id,
                manufacturer=manufacturer.id,
                discovered=True,
                tags=[{'name': INVENTORY_TAG['gpu']['name']}],
                name=gpu['product'],
                description=gpu['description'],
            )

            logging.info('Creating GPU model {}'.format(gpu['product']))

    def is_external_gpu(self, gpu):
        is_3d_gpu = gpu['description'].startswith('3D')
        return self.server.is_blade() and \
            self.server.own_gpu_expansion_slot() and is_3d_gpu

    def do_netbox_gpus(self):
        gpus = []
        gpu_models = {}
        for gpu in  self.lshw.get_hw_linux('gpu'):
            # Filters GPU if an expansion bay is detected:
            # The internal (VGA) GPU only goes into the blade inventory,
            # the external (3D) GPU goes into the expansion blade.
            if config.expansion_as_device and \
                    self.update_expansion ^ self.is_external_gpu(gpu):
                continue
            gpus.append(gpu)
            gpu_models.setdefault(gpu["product"], 0)
            gpu_models[gpu["product"]] += 1

        nb_gpus = self.get_netbox_inventory(
            device_id=self.device_id,
            tag=INVENTORY_TAG['gpu']['slug'],
        )
        nb_gpu_models = {}
        for gpu in nb_gpus:
            nb_gpu_models.setdefault(str(gpu), 0)
            nb_gpu_models[str(gpu)] += 1
        up_to_date = set(gpu_models) == set(nb_gpu_models)
        if not gpus or not up_to_date:
            for x in nb_gpus:
                x.delete()
        if gpus and not up_to_date:
            self.create_netbox_gpus(gpus)

    def create_or_update(self):
        if config.inventory is None or config.update_inventory is None:
            return False
        if self.update_expansion is False:
            self.do_netbox_cpus()
            self.do_netbox_memories()
            self.do_netbox_interfaces()
            self.do_netbox_motherboard()
        self.do_netbox_gpus()
        self.do_netbox_disks()
        self.do_netbox_raid_cards()
        return True
