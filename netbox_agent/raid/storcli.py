import json
import subprocess

from netbox_agent.misc import get_vendor
from netbox_agent.raid.base import Raid, RaidController


class StorcliController(RaidController):
    def __init__(self, controller_index, data):
        self.data = data
        self.controller_index = controller_index

    def get_product_name(self):
        return self.data['Product Name']

    def get_manufacturer(self):
        return None

    def get_serial_number(self):
        return self.data['Serial Number']

    def get_firmware_version(self):
        return self.data['FW Package Build']

    def get_physical_disks(self):
        ret = []
        output = subprocess.getoutput(
            'storcli /c{}/eall/sall show all J'.format(self.controller_index)
        )
        drive_infos = json.loads(output)['Controllers'][self.controller_index]['Response Data']

        for physical_drive in self.data['PD LIST']:
            enclosure = physical_drive.get('EID:Slt').split(':')[0]
            slot = physical_drive.get('EID:Slt').split(':')[1]
            size = physical_drive.get('Size').strip()
            media_type = physical_drive.get('Med').strip()
            drive_identifier = 'Drive /c{}/e{}/s{}'.format(
                str(self.controller_index), str(enclosure), str(slot)
            )
            drive_attr = drive_infos['{} - Detailed Information'.format(drive_identifier)][
                '{} Device attributes'.format(drive_identifier)]
            model = drive_attr.get('Model Number', '').strip()
            ret.append({
                'Model': model,
                'Vendor': get_vendor(model),
                'SN': drive_attr.get('SN', '').strip(),
                'Size': size,
                'Type': media_type,
                '_src': self.__class__.__name__,
            })
        return ret


class StorcliRaid(Raid):
    def __init__(self):
        self.output = subprocess.getoutput('storcli /call show J')
        self.data = json.loads(self.output)
        self.controllers = []

        if len([
                x for x in self.data['Controllers']
                if x['Command Status']['Status'] == 'Success'
        ]) > 0:
            for controller in self.data['Controllers']:
                self.controllers.append(
                    StorcliController(
                        controller['Command Status']['Controller'],
                        controller['Response Data']
                    )
                )

    def get_controllers(self):
        return self.controllers
