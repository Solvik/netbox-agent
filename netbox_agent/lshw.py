from netbox_agent.misc import is_tool
import subprocess
import logging
import json
import sys
import re


class LSHW:
    def __init__(self):
        if not is_tool("lshw"):
            logging.error("lshw does not seem to be installed")
            sys.exit(1)

        data = subprocess.getoutput("lshw -quiet -json")
        json_data = json.loads(data)
        # Starting from version 02.18, `lshw -json` wraps its result in a list
        # rather than returning directly a dictionary
        if isinstance(json_data, list):
            self.hw_info = json_data[0]
        else:
            self.hw_info = json_data
        self.info = {}
        self.memories = []
        self.interfaces = []
        self.cpus = []
        self.power = []
        self.disks = []
        self.gpus = []
        if hasattr(self.hw_info, "vendor"): 
            vendor = self.hw_info["vendor"]
        else:
            vendor = "Not Specified"
        self.vendor = vendor
        self.product = self.hw_info["product"]
        self.chassis_serial = self.hw_info["serial"]
        self.motherboard_serial = self.hw_info["children"][0].get("serial", "No S/N")
        self.motherboard = self.hw_info["children"][0].get("product", "Motherboard")

        for k in self.hw_info["children"]:
            if k["class"] == "power":
                # self.power[k["id"]] = k
                self.power.append(k)

            if "children" in k:
                for j in k["children"]:
                    if j["class"] == "generic":
                        continue

                    if j["class"] == "storage":
                        self.find_storage(j)

                    if j["class"] == "memory":
                        self.find_memories(j)

                    if j["class"] == "processor":
                        self.find_cpus(j)

                    if j["class"] == "bridge":
                        self.walk_bridge(j)

    def get_hw_linux(self, hwclass):
        if hwclass == "cpu":
            return self.cpus
        if hwclass == "gpu":
            return self.gpus
        if hwclass == "network":
            return self.interfaces
        if hwclass == "storage":
            return self.disks
        if hwclass == "memory":
            return self.memories

    def find_network(self, obj):
        # Some interfaces do not have device (logical) name (eth0, for
        # instance), such as not connected network mezzanine cards in blade
        # servers. In such situations, the card will be named `unknown[0-9]`.
        unkn_intfs = []
        for i in self.interfaces:
            # newer versions of lshw can return a list of names, see issue #227
            if not isinstance(i["name"], list):
                if i["name"].startswith("unknown"):
                    unkn_intfs.append(i)
            else:
                for j in i["name"]:
                    if j.startswith("unknown"):
                        unkn_intfs.append(j)

        unkn_name = "unknown{}".format(len(unkn_intfs))
        self.interfaces.append(
            {
                "name": obj.get("logicalname", unkn_name),
                "macaddress": obj.get("serial", ""),
                "serial": obj.get("serial", ""),
                "product": obj.get("product", "Unknown NIC"),
                "vendor": obj.get("vendor", "Unknown"),
                "description": obj.get("description", ""),
            }
        )

    def find_storage(self, obj):
        if "driver" in obj["configuration"] and "nvme" in obj["configuration"]["driver"]:
            if not is_tool("nvme"):
                logging.error("nvme-cli >= 1.0 does not seem to be installed")
                return
            try:
                nvme = json.loads(
                    subprocess.check_output(["nvme", "-list", "-o", "json"], encoding="utf8")
                )
                for device in nvme["Devices"]:
                    d = {
                        "logicalname": device["DevicePath"],
                        "product": device["ModelNumber"],
                        "serial": device["SerialNumber"],
                        "version": device["Firmware"],
                        "description": "NVME",
                        "type": "NVME",
                    }
                    if "UsedSize" in device:
                        d["size"] = device["UsedSize"]
                    if "UsedBytes" in device:
                        d["size"] = device["UsedBytes"]
                    self.disks.append(d)
            except Exception:
                pass
        elif "children" in obj:
            for device in obj["children"]:
                self.disks.append(
                    {
                        "logicalname": device.get("logicalname"),
                        "product": device.get("product"),
                        "serial": device.get("serial"),
                        "version": device.get("version"),
                        "size": device.get("size"),
                        "description": device.get("description"),
                        "type": device.get("description"),
                    }
                )

    def find_cpus(self, obj):
        if "product" in obj:
            if (bool(re.search(r'cpu\:\d', obj.get("id"))) and obj.get("product") == "cpu"):
                # First trey to get more information with lscpu
                vendor_name = "Unknown vendor"
                cpu_name = "Unknown CPU"
                description_detail = ""
                if not is_tool("lscpu"):
                    logging.error("lscpu does not seem to be installed")
                try:
                    lscpu = json.loads(
                        subprocess.check_output(["lscpu", "-J"], encoding="utf8")
                    )
                    for device in lscpu["lscpu"]:
                        if device["field"] == "Vendor ID:":
                            vendor_name = device["data"]
                        if device["field"] == "Model name:":
                            cpu_name = device["data"]
                        if device["field"] == "Architecture:":
                            description_detail = description_detail + "Architecture: " +  device["data"] + " "
                        if device["field"] == "Flags:":
                            description_detail = description_detail + "Flags: " + device["data"]
                except Exception:
                    pass

                # In this case each CPU core is counted as a separate entity; overwrite cputoappend entity
                temp_cpu_name = obj.get("product", cpu_name)
                temp_description = obj.get("description", description_detail),
                if temp_cpu_name == "cpu" and cpu_name != "Unknown CPU":
                    # cpu this is the default name, dont use it if better data is available
                    temp_cpu_name = cpu_name
                if temp_description[0] == "CPU" and description_detail != "":
                    # CPU this is the default description, dont use it if better data is available
                    temp_description = description_detail
                self.cpus = [ {
                        "product": temp_cpu_name + " (" + str(int(obj.get("id").split(":")[1])+1) + " Core, " + str(obj.get("size")/1000000) + " MHz)",
                        "vendor": obj.get("vendor", vendor_name),
                        "description": temp_description,
                        "location": obj.get("slot", ""),
                    }]
            else:
                self.cpus.append(
                    {
                        "product": obj.get("product", "Unknown CPU"),
                        "vendor": obj.get("vendor", "Unknown vendor"),
                        "description": obj.get("description", ""),
                        "location": obj.get("slot", ""),
                    }
                )

    def find_memories(self, obj):
        if "children" not in obj:
            if obj.get("description") ==  "System memory":
                self.memories.append(
                {
                    # This is probably embedded memory as for a Raspberry pi
                    "slot": obj.get("slot", "Integrated Memory"),
                    "description": obj.get("description"),
                    "id": obj.get("id"),
                    "serial": obj.get("serial", "N/A"),
                    "vendor": obj.get("vendor", "N/A"),
                    "product": obj.get("product", "N/A"),
                    "size": obj.get("size", 0) / 2**20 / 1024,
                })
                return
            else:
                # print("not a DIMM memory or integrated memory.")
                return

        for dimm in obj["children"]:
            if "empty" in dimm["description"]:
                continue

            self.memories.append(
                {
                    "slot": dimm.get("slot"),
                    "description": dimm.get("description"),
                    "id": dimm.get("id"),
                    "serial": dimm.get("serial", "N/A"),
                    "vendor": dimm.get("vendor", "N/A"),
                    "product": dimm.get("product", "N/A"),
                    "size": dimm.get("size", 0) / 2**20 / 1024,
                }
            )

    def find_gpus(self, obj):
        if "product" in obj:
            infos = {
                "product": obj.get("product", "Unknown GPU"),
                "vendor": obj.get("vendor", "Unknown"),
                "description": obj.get("description", ""),
            }
            self.gpus.append(infos)

    def walk_bridge(self, obj):
        if "children" not in obj:
            return

        for bus in obj["children"]:
            if bus["class"] == "storage":
                self.find_storage(bus)
            if bus["class"] == "display":
                self.find_gpus(bus)

            if "children" in bus:
                for b in bus["children"]:
                    if b["class"] == "storage":
                        self.find_storage(b)
                    if b["class"] == "network":
                        self.find_network(b)
                    if b["class"] == "display":
                        self.find_gpus(b)


if __name__ == "__main__":
    pass
