from netbox_agent.raid.base import Raid, RaidController
from netbox_agent.misc import get_vendor, get_mount_points
from netbox_agent.config import config
import subprocess
import logging
import json
import re
import os


class StorcliControllerError(Exception):
    pass


def storecli(sub_command):
    command = ["storcli"]
    command.extend(sub_command.split())
    command.append("J")
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    stdout, stderr = p.communicate()
    if stderr:
        mesg = "Failed to execute command '{}':\n{}".format(" ".join(command), stdout)
        raise StorcliControllerError(mesg)

    stdout = stdout.decode("utf-8")
    data = json.loads(stdout)

    controllers = dict(
        [
            (c["Command Status"]["Controller"], c["Response Data"])
            for c in data["Controllers"]
            if c["Command Status"]["Status"] == "Success"
        ]
    )
    if not controllers:
        logging.error(
            "Failed to execute command '{}'. " "Ignoring data.".format(" ".join(command))
        )
        return {}
    return controllers


class StorcliController(RaidController):
    def __init__(self, controller_index, data):
        self.data = data
        self.controller_index = controller_index

    def get_product_name(self):
        return self.data["Product Name"]

    def get_manufacturer(self):
        return None

    def get_serial_number(self):
        return self.data["Serial Number"]

    def get_firmware_version(self):
        return self.data["FW Package Build"]

    def _get_physical_disks(self):
        pds = {}
        cmd = "/c{}/eall/sall show all".format(self.controller_index)
        controllers = storecli(cmd)
        pd_info = controllers[self.controller_index]
        pd_re = re.compile(r"^Drive (/c\d+/e\d+/s\d+)$")

        for section, attrs in pd_info.items():
            reg = pd_re.search(section)
            if reg is None:
                continue
            pd_name = reg.group(1)
            pd_attr = attrs[0]
            pd_identifier = pd_attr["EID:Slt"]
            size = pd_attr.get("Size", "").strip()
            media_type = pd_attr.get("Med", "").strip()
            pd_details = pd_info["{} - Detailed Information".format(section)]
            pd_dev_attr = pd_details["{} Device attributes".format(section)]
            model = pd_dev_attr.get("Model Number", "").strip()
            pd = {
                "Model": model,
                "Vendor": get_vendor(model),
                "SN": pd_dev_attr.get("SN", "").strip(),
                "Size": size,
                "Type": media_type,
                "_src": self.__class__.__name__,
            }
            if config.process_virtual_drives:
                pd.setdefault("custom_fields", {})["pd_identifier"] = pd_name
            pds[pd_identifier] = pd
        return pds

    def _get_virtual_drives_map(self):
        vds = {}
        cmd = "/c{}/vall show all".format(self.controller_index)
        controllers = storecli(cmd)
        vd_info = controllers[self.controller_index]
        mount_points = get_mount_points()

        for vd_identifier, vd_attrs in vd_info.items():
            if not vd_identifier.startswith("/c{}/v".format(self.controller_index)):
                continue
            volume = vd_identifier.split("/")[-1].lstrip("v")
            vd_attr = vd_attrs[0]
            vd_pd_identifier = "PDs for VD {}".format(volume)
            vd_pds = vd_info[vd_pd_identifier]
            vd_prop_identifier = "VD{} Properties".format(volume)
            vd_properties = vd_info[vd_prop_identifier]
            for pd in vd_pds:
                pd_identifier = pd["EID:Slt"]
                wwn = vd_properties["SCSI NAA Id"]
                wwn_path = "/dev/disk/by-id/wwn-0x{}".format(wwn)
                device = os.path.realpath(wwn_path)
                mp = mount_points.get(device, "n/a")
                vds[pd_identifier] = {
                    "vd_array": vd_identifier,
                    "vd_size": vd_attr["Size"],
                    "vd_consistency": vd_attr["Consist"],
                    "vd_raid_type": vd_attr["TYPE"],
                    "vd_device": device,
                    "mount_point": ", ".join(sorted(mp)),
                }
        return vds

    def get_physical_disks(self):
        # Parses physical disks information
        pds = self._get_physical_disks()

        # Parses virtual drives information and maps them to physical disks
        vds = self._get_virtual_drives_map()
        for pd_identifier, vd in vds.items():
            if pd_identifier not in pds:
                logging.error(
                    "Physical drive {} listed in virtual drive {} not "
                    "found in drives list".format(pd_identifier, vd["vd_array"])
                )
                continue
            pds[pd_identifier].setdefault("custom_fields", {}).update(vd)

        return list(pds.values())


class StorcliRaid(Raid):
    def __init__(self):
        self.controllers = []
        controllers = storecli("/call show")
        for controller_id, controller_data in controllers.items():
            self.controllers.append(StorcliController(controller_id, controller_data))

    def get_controllers(self):
        return self.controllers
