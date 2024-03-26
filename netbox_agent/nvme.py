import logging
import subprocess
import json

from netbox_agent.misc import is_tool


class LLDP():
    def __init__(self, output=None):
        if not is_tool('nvme'):
            logging.debug('nvme-cli package seems to be missing.')
        if output:
            self.output = output
        else:
            self.output = subprocess.getoutput('nvme list --output-format=json')
        self.data = self.parse()
    
    def parse(self):
        parsed_data = []
        try:
            json_data = json.loads(self.output)
            for device in json_data['Devices']:
                parsed_device = {
                    "NameSpace": device.get('NameSpace'),
                    "DevicePath": device.get('DevicePath'),
                    "Firmware": device.get('Firmware'),
                    "ModelNumber": device.get('ModelNumber'),
                    "SerialNumber": device.get('SerialNumber'),
                    "UsedBytes": device.get('UsedBytes'),
                    "MaximumLBA": device.get('MaximumLBA'),
                    "PhysicalSize": device.get('PhysicalSize'),
                    "SectorSize": device.get('SectorSize')
                }
                parsed_data.append(parsed_device)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON output: {e}")
        return parsed_data