import re
import subprocess
import xml.etree.ElementTree as ET  # NOQA

from netbox_agent.misc import get_vendor
from netbox_agent.raid.base import Raid, RaidController

# Inspiration from https://github.com/asciiphil/perc-status/blob/master/perc-status


def get_field(obj, fieldname):
    f = obj.find(fieldname)
    if f is None:
        return None
    if f.attrib['type'] in ['u32', 'u64']:
        if re.search('Mask$', fieldname):
            return int(f.text, 2)
        else:
            return int(f.text)
    if f.attrib['type'] == 'astring':
        return f.text
    return f.text


class OmreportController(RaidController):
    def __init__(self, controller_index, data):
        self.data = data
        self.controller_index = controller_index

    def get_product_name(self):
        return get_field(self.data, 'Name')

    def get_manufacturer(self):
        return None

    def get_serial_number(self):
        return get_field(self.data, 'DeviceSerialNumber')

    def get_firmware_version(self):
        return get_field(self.data, 'Firmware Version')

    def get_physical_disks(self):
        ret = []
        output = subprocess.getoutput(
            'omreport storage controller controller={} -fmt xml'.format(self.controller_index)
        )
        root = ET.fromstring(output)
        et_array_disks = root.find('ArrayDisks')
        if et_array_disks is not None:
            for obj in et_array_disks.findall('DCStorageObject'):
                ret.append({
                    'Vendor': get_vendor(get_field(obj, 'Vendor')),
                    'Model': get_field(obj, 'ProductID'),
                    'SN': get_field(obj, 'DeviceSerialNumber'),
                    'Size': '{:.0f}GB'.format(
                        int(get_field(obj, 'Length')) / 1024 / 1024 / 1024
                    ),
                    'Type': 'HDD' if int(get_field(obj, 'MediaType')) == 1 else 'SSD',
                    '_src': self.__class__.__name__,
                })
        return ret


class OmreportRaid(Raid):
    def __init__(self):
        output = subprocess.getoutput('omreport storage controller -fmt xml')
        controller_xml = ET.fromstring(output)
        self.controllers = []

        for obj in controller_xml.find('Controllers').findall('DCStorageObject'):
            ctrl_index = get_field(obj, 'ControllerNum')
            self.controllers.append(
                OmreportController(ctrl_index, obj)
            )

    def get_controllers(self):
        return self.controllers
