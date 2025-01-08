from netbox_agent.raid.base import Raid, RaidController
from netbox_agent.misc import get_vendor, get_mount_points
from netbox_agent.config import config
import subprocess
import logging
import re


class OmreportControllerError(Exception):
    pass


def omreport(sub_command):
    command = ["omreport"]
    command.extend(sub_command.split())
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    p.wait()
    stdout = p.stdout.read().decode("utf-8")
    if p.returncode != 0:
        mesg = "Failed to execute command '{}':\n{}".format(" ".join(command), stdout)
        raise OmreportControllerError(mesg)

    res = {}
    section_re = re.compile("^[A-Z]")
    current_section = None
    current_obj = None

    for line in stdout.split("\n"):
        if ": " in line:
            attr, value = line.split(": ", 1)
            attr = attr.strip()
            value = value.strip()
            if attr == "ID":
                obj = {}
                res.setdefault(current_section, []).append(obj)
                current_obj = obj
            current_obj[attr] = value
        elif section_re.search(line) is not None:
            current_section = line.strip()
    return res


class OmreportController(RaidController):
    def __init__(self, controller_index, data):
        self.data = data
        self.controller_index = controller_index

    def get_product_name(self):
        return self.data["Name"]

    def get_manufacturer(self):
        return None

    def get_serial_number(self):
        return self.data.get("DeviceSerialNumber")

    def get_firmware_version(self):
        return self.data.get("Firmware Version")

    def _get_physical_disks(self):
        pds = {}
        res = omreport("storage pdisk controller={}".format(self.controller_index))
        for pdisk in [d for d in list(res.values())[0]]:
            disk_id = pdisk["ID"]
            size = re.sub("B .*$", "B", pdisk["Capacity"])
            pds[disk_id] = {
                "Vendor": get_vendor(pdisk["Vendor ID"]),
                "Model": pdisk["Product ID"],
                "SN": pdisk["Serial No."],
                "Size": size,
                "Type": pdisk["Media"],
                "_src": self.__class__.__name__,
            }
        return pds

    def _get_virtual_drives_map(self):
        pds = {}
        res = omreport("storage vdisk controller={}".format(self.controller_index))
        for vdisk in [d for d in list(res.values())[0]]:
            vdisk_id = vdisk["ID"]
            device = vdisk["Device Name"]
            mount_points = get_mount_points()
            mp = mount_points.get(device, "n/a")
            size = re.sub("B .*$", "B", vdisk["Size"])
            vd = {
                "vd_array": vdisk_id,
                "vd_size": size,
                "vd_consistency": vdisk["State"],
                "vd_raid_type": vdisk["Layout"],
                "vd_device": vdisk["Device Name"],
                "mount_point": ", ".join(sorted(mp)),
            }
            drives_res = omreport(
                "storage pdisk controller={} vdisk={}".format(self.controller_index, vdisk_id)
            )
            for pdisk in [d for d in list(drives_res.values())[0]]:
                pds[pdisk["ID"]] = vd
        return pds

    def get_physical_disks(self):
        pds = self._get_physical_disks()
        vds = self._get_virtual_drives_map()
        for pd_identifier, vd in vds.items():
            if pd_identifier not in pds:
                logging.error(
                    "Physical drive {} listed in virtual drive {} not "
                    "found in drives list".format(pd_identifier, vd["vd_array"])
                )
                continue
            pds[pd_identifier].setdefault("custom_fields", {}).update(vd)
            pds[pd_identifier]["custom_fields"]["pd_identifier"] = pd_identifier
        return list(pds.values())


class OmreportRaid(Raid):
    def __init__(self):
        self.controllers = []
        res = omreport("storage controller")

        for controller in res["Controller"]:
            ctrl_index = controller["ID"]
            self.controllers.append(OmreportController(ctrl_index, controller))

    def get_controllers(self):
        return self.controllers
