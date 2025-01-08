from netbox_agent.raid.base import Raid, RaidController
from netbox_agent.misc import get_vendor
from netbox_agent.config import config
import subprocess
import logging
import re

REGEXP_CONTROLLER_HP = re.compile(r"Smart Array ([a-zA-Z0-9- ]+) in Slot ([0-9]+)")


class HPRaidControllerError(Exception):
    pass


def ssacli(sub_command):
    command = ["ssacli"]
    command.extend(sub_command.split())
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = p.communicate()
    stdout = stdout.decode("utf-8")
    if p.returncode != 0:
        mesg = "Failed to execute command '{}':\n{}".format(" ".join(command), stdout)
        raise HPRaidControllerError(mesg)

    if "does not have any physical" in stdout:
        return list()
    else:
        lines = stdout.split("\n")
        lines = list(filter(None, lines))
        return lines


def _test_if_valid_line(line):
    ignore_patterns = ["Note:", "Error:", "is not loaded", "README", " failure", " cache"]
    for pattern in ignore_patterns:
        if not line or pattern in line:
            return None
    return line


def _parse_ctrl_output(lines):
    controllers = {}
    current_ctrl = None

    for line in lines:
        line = line.strip()
        line = _test_if_valid_line(line)
        if line is None:
            continue
        ctrl = REGEXP_CONTROLLER_HP.search(line)
        if ctrl is not None:
            slot = ctrl.group(2)
            current_ctrl = "{} - Slot {}".format(ctrl.group(1), slot)
            controllers[current_ctrl] = {"Slot": slot}
            if "Embedded" not in line:
                controllers[current_ctrl]["External"] = True
                continue
        if ": " not in line:
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
        line = _test_if_valid_line(line)
        if line is None:
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
        attr = attr.strip()
        val = val.strip()
        drives.setdefault(current_drv, {})[attr] = val
    return drives


def _parse_ld_output(lines):
    drives = {}
    current_array = None
    current_drv = None

    for line in lines:
        line = line.strip()
        line = _test_if_valid_line(line)
        if line is None:
            continue
        # Parses the Array the drives are in
        if line.startswith("Array"):
            current_array = line.split(None, 1)[1]
            drives[current_array] = {}
        # Detects new physical drive
        if line.startswith("Logical Drive"):
            current_drv = line.split(": ", 1)[1]
            drives.setdefault(current_array, {})["LogicalDrive"] = current_drv
            continue
        if ": " not in line:
            continue
        attr, val = line.split(": ", 1)
        drives.setdefault(current_array, {})[attr] = val
    return drives


class HPRaidController(RaidController):
    def __init__(self, controller_name, data):
        self.controller_name = controller_name
        self.data = data
        self.pdrives = self._get_physical_disks()
        arrays = [d["Array"] for d in self.pdrives.values() if d.get("Array")]
        if arrays:
            self.ldrives = self._get_logical_drives()
            self._get_virtual_drives_map()

    def get_product_name(self):
        return self.controller_name

    def get_manufacturer(self):
        return "HP"

    def get_serial_number(self):
        return self.data["Serial Number"]

    def get_firmware_version(self):
        return self.data["Firmware Version"]

    def is_external(self):
        return self.data.get("External", False)

    def _get_physical_disks(self):
        lines = ssacli("ctrl slot={} pd all show detail".format(self.data["Slot"]))
        pdrives = _parse_pd_output(lines)
        ret = {}

        for name, attrs in pdrives.items():
            array = attrs.get("Array", "")
            model = attrs.get("Model", "").strip()
            vendor = None
            if model.startswith("HP"):
                vendor = "HP"
            elif len(model.split()) > 1:
                vendor = get_vendor(model.split()[1])
            else:
                vendor = get_vendor(model)

            ret[name] = {
                "Array": array,
                "Model": model,
                "Vendor": vendor,
                "SN": attrs.get("Serial Number", "").strip(),
                "Size": attrs.get("Size", "").strip(),
                "Type": "SSD" if attrs.get("Interface Type") == "Solid State SATA" else "HDD",
                "_src": self.__class__.__name__,
                "custom_fields": {
                    "pd_identifier": name,
                    "mount_point": attrs.get("Mount Points", "").strip(),
                    "vd_device": attrs.get("Disk Name", "").strip(),
                    "vd_size": attrs.get("Size", "").strip(),
                },
            }
        return ret

    def _get_logical_drives(self):
        lines = ssacli("ctrl slot={} ld all show detail".format(self.data["Slot"]))
        ldrives = _parse_ld_output(lines)
        ret = {}

        for array, attrs in ldrives.items():
            ret[array] = {
                "vd_array": array,
                "vd_size": attrs.get("Size", "").strip(),
                "vd_consistency": attrs.get("Status", "").strip(),
                "vd_raid_type": "RAID {}".format(attrs.get("Fault Tolerance", "N/A").strip()),
                "vd_device": attrs.get("LogicalDrive", "").strip(),
                "mount_point": attrs.get("Mount Points", "").strip(),
            }
        return ret

    def _get_virtual_drives_map(self):
        for name, attrs in self.pdrives.items():
            array = attrs["Array"]
            ld = self.ldrives.get(array)
            if ld is None:
                logging.error(
                    "Failed to find array information for physical drive {}." " Ignoring.".format(
                        name
                    )
                )
                continue
            attrs["custom_fields"].update(ld)

    def get_physical_disks(self):
        return list(self.pdrives.values())


class HPRaid(Raid):
    def __init__(self):
        self.output = subprocess.getoutput("ssacli ctrl all show detail")
        self.controllers = []
        self.convert_to_dict()

    def convert_to_dict(self):
        lines = self.output.split("\n")
        lines = list(filter(None, lines))
        controllers = _parse_ctrl_output(lines)
        for controller, attrs in controllers.items():
            self.controllers.append(HPRaidController(controller, attrs))

    def get_controllers(self):
        return self.controllers
