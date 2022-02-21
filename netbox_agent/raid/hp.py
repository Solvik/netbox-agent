import re
import subprocess

from netbox_agent.config import config
from netbox_agent.misc import get_vendor
from netbox_agent.raid.base import Raid, RaidController

REGEXP_CONTROLLER_HP = re.compile(r'Smart Array ([a-zA-Z0-9- ]+) in Slot ([0-9]+)')


def _parse_ctrl_output(lines):
    controllers = {}
    current_ctrl = None

    for line in lines:
        if not line or line.startswith('Note:'):
            continue
        ctrl = REGEXP_CONTROLLER_HP.search(line)
        if ctrl is not None:
            current_ctrl = ctrl.group(1)
            controllers[current_ctrl] = {"Slot": ctrl.group(2)}
            if "Embedded" not in line:
                controllers[current_ctrl]["External"] = True
            continue
        attr, val = line.split(": ", 1)
        attr = attr.strip()
        val = val.strip()
        controllers[current_ctrl][attr] = val
    return controllers


def _parse_pd_output(lines):
    drives = {}
    current_array = None
    current_drv = None

    for line in lines:
        line = line.strip()
        if not line or line.startswith('Note:'):
            continue
        # Parses the Array the drives are in
        if line.startswith("Array"):
            current_array = line.split(None, 1)[1]
        # Detects new physical drive
        if line.startswith("physicaldrive"):
            current_drv = line.split(None, 1)[1]
            drives[current_drv] = {}
            if current_array is not None:
                drives[current_drv]["Array"] = current_array
            continue
        if ": " not in line:
            continue
        attr, val = line.split(": ", 1)
        drives.setdefault(current_drv, {})[attr] = val
    return drives


class HPRaidController(RaidController):
    def __init__(self, controller_name, data):
        self.controller_name = controller_name
        self.data = data
        self.drives = self._get_physical_disks()

    def get_product_name(self):
        return self.controller_name

    def get_manufacturer(self):
        return 'HP'

    def get_serial_number(self):
        return self.data['Serial Number']

    def get_firmware_version(self):
        return self.data['Firmware Version']

    def is_external(self):
        return self.data.get('External', False)

    def _get_physical_disks(self):
        output = subprocess.getoutput(
            'ssacli ctrl slot={slot} pd all show detail'.format(slot=self.data['Slot'])
        )
        lines = output.split('\n')
        lines = list(filter(None, lines))
        drives = _parse_pd_output(lines)
        ret = []

        for name, attrs in drives.items():
            model = attrs.get('Model', '').strip()
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
                'SN': attrs.get('Serial Number', '').strip(),
                'Size': attrs.get('Size', '').strip(),
                'Type': 'SSD' if attrs.get('Interface Type') == 'Solid State SATA'
                else 'HDD',
                '_src': self.__class__.__name__,
            })
        return ret

    def get_physical_disks(self):
        return self.drives


class HPRaid(Raid):
    def __init__(self):
        self.output = subprocess.getoutput('ssacli ctrl all show detail')
        self.controllers = []
        self.convert_to_dict()

    def convert_to_dict(self):
        lines = self.output.split('\n')
        lines = list(filter(None, lines))
        controllers = _parse_ctrl_output(lines)
        for controller, attrs in controllers.items():
            self.controllers.append(
                HPRaidController(controller, attrs)
            )

    def get_controllers(self):
        return self.controllers
