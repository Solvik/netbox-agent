import subprocess
import json

from netbox_agent.raid.base import Raid, RaidController

class StorcliController(RaidController):
    def __init__(self, data):
        self.data = data

    def get_product_name(self):
        return self.data['Product Name']

    def get_manufacturer(self):
        return None

    def get_serial_number(self):
        return self.data['Serial Number']

    def get_firmware_version(self):
        return self.data['FW Package Build']

class StorcliRaid(Raid):
    def __init__(self):
        self.output = subprocess.getoutput('storcli /call show J')
        self.data = json.loads(self.output)
        self.controllers = []

        if len([
                x for x in self.data['Controllers'] \
                if x['Command Status']['Status'] == 'Success'
        ]) > 0:
            for controller in self.data['Controllers']:
                self.controllers.append(
                    StorcliController(controller['Response Data'])
                )

    def get_controllers(self):
        return self.controllers
