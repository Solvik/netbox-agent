import re
import subprocess

from netbox_agent.misc import get_vendor
from netbox_agent.raid.base import Raid, RaidController

REGEXP_CONTROLLER_HP = re.compile(r'Smart Array ([a-zA-Z0-9- ]+) in Slot ([0-9]+)')


def _get_indentation(string):
    """Return the number of spaces before the current line."""
    return len(string) - len(string.lstrip(' '))


def _get_key_value(string):
    """Return the (key, value) as a tuple from a string."""
    # Normally all properties look like this:
    #   Unique Identifier: 600508B1001CE4ACF473EE9C826230FF
    #   Disk Name: /dev/sda
    #   Mount Points: None
    key = ''
    value = ''
    try:
        key, value = string.split(':')
    except ValueError:
        # This handles the case when the property of a logical drive
        # returned is as follows. Here we cannot split by ':' because
        # the disk id has colon in it. So if this is about disk,
        # then strip it accordingly.
        #   Mirror Group 0: physicaldrive 6I:1:5
        string = string.lstrip(' ')
        if string.startswith('physicaldrive'):
            fields = string.split(' ')
            key = fields[0]
            value = fields[1]
        else:
            # TODO(rameshg87): Check if this ever occurs.
            return None, None

    return key.lstrip(' ').rstrip(' '), value.lstrip(' ').rstrip(' ')


def _get_dict(lines, start_index, indentation):
    """Recursive function for parsing hpssacli/ssacli output."""

    info = {}
    current_item = None

    i = start_index
    while i < len(lines):
        current_line = lines[i]
        if current_line.startswith('Note:'):
            i = i + 1
            continue

        current_line_indentation = _get_indentation(current_line)
        # This check ignore some useless information that make
        # crash the parsing
        product_name = REGEXP_CONTROLLER_HP.search(current_line)
        if current_line_indentation == 0 and not product_name:
            i = i + 1
            continue

        if current_line_indentation == indentation:
            current_item = current_line.lstrip(' ')

            info[current_item] = {}
            i = i + 1
            continue

        if i >= len(lines) - 1:
            key, value = _get_key_value(current_line)
            # If this is some unparsable information, then
            # just skip it.
            if key:
                info[current_item][key] = value
            return info, i

        next_line = lines[i + 1]
        next_line_indentation = _get_indentation(next_line)

        if current_line_indentation == next_line_indentation:
            key, value = _get_key_value(current_line)
            if key:
                info[current_item][key] = value
            i = i + 1
        elif next_line_indentation > current_line_indentation:
            ret_dict, j = _get_dict(lines, i, current_line_indentation)
            info[current_item].update(ret_dict)
            i = j + 1
        elif next_line_indentation < current_line_indentation:
            key, value = _get_key_value(current_line)
            if key:
                info[current_item][key] = value
            return info, i

    return info, i


class HPRaidController(RaidController):
    def __init__(self, controller_name, data):
        self.controller_name = controller_name
        self.data = data

    def get_product_name(self):
        return self.controller_name

    def get_manufacturer(self):
        return 'HP'

    def get_serial_number(self):
        return self.data['Serial Number']

    def get_firmware_version(self):
        return self.data['Firmware Version']

    def get_physical_disks(self):
        ret = []
        output = subprocess.getoutput(
            'ssacli ctrl slot={slot} pd all show detail'.format(slot=self.data['Slot'])
        )
        lines = output.split('\n')
        lines = list(filter(None, lines))
        j = -1
        while j < len(lines):
            info_dict, j = _get_dict(lines, j + 1, 0)

        key = next(iter(info_dict))
        for array, physical_disk in info_dict[key].items():
            for _, pd_attr in physical_disk.items():
                model = pd_attr.get('Model', '').strip()
                vendor = None
                if model.startswith('HP'):
                    vendor = 'HP'
                elif len(model.split()) > 1:
                    vendor = get_vendor(model.split()[1])
                else:
                    vendor = get_vendor(model)

                ret.append({
                    'Model': model,
                    'Vendor': vendor,
                    'SN': pd_attr.get('Serial Number', '').strip(),
                    'Size': pd_attr.get('Size', '').strip(),
                    'Type': 'SSD' if pd_attr.get('Interface Type') == 'Solid State SATA'
                    else 'HDD',
                    '_src': self.__class__.__name__,
                })
        return ret


class HPRaid(Raid):
    def __init__(self):
        self.output = subprocess.getoutput('ssacli ctrl all show detail')
        self.controllers = []
        self.convert_to_dict()

    def convert_to_dict(self):
        lines = self.output.split('\n')
        lines = list(filter(None, lines))
        j = -1
        while j < len(lines):
            info_dict, j = _get_dict(lines, j + 1, 0)
            if len(info_dict.keys()):
                _product_name = list(info_dict.keys())[0]
                product_name = REGEXP_CONTROLLER_HP.search(_product_name)
                if product_name:
                    self.controllers.append(
                        HPRaidController(product_name.group(1), info_dict[_product_name])
                    )

    def get_controllers(self):
        return self.controllers
