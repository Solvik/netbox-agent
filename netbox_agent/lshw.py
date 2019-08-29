import logging

import subprocess
import getpass
import json

from pprint import pprint

class LSHW():
    def __init__(self, device_id):

        self.hw_info = json.loads(subprocess.check_output(["lshw", "-quiet", "-json"],encoding='utf8'))

        self.info = {}
        self.memories = []
        self.interfaces = []
        self.cpus = []
        self.power = []
        self.disks = []
        self.vendor = self.hw_info["vendor"]
        self.product = self.hw_info["product"]
        self.chassis_serial = self.hw_info["serial"]
        self.motherboard_serial = self.hw_info["children"][0]["serial"]
        self.motherboard = self.hw_info["children"][0]["product"]
        self.device_id = device_id

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

    def get_hw_linux(self, hwclass, device_id):
        if hwclass == "cpu":
            return self.cpus
        if hwclass == "network":
            return self.interfaces
        if hwclass == 'storage':
            return self.disks
        if hwclass == 'memory':
            return self.memories

    def find_network(self, obj):
        d = {}
        d["bus info"] = "%s@%s" % ( self.device_id, obj["logicalname"])
        d["name"] = obj["logicalname"]
        d["macaddress"] = obj["serial"]
        d["serial"] = obj["serial"]
        d["product"] = obj["product"]
        d["vendor"] = obj["vendor"]
        d["description"] = obj["description"]

        self.interfaces.append(d)

    def find_storage(self, obj):
        if "children" in obj:
            for device in obj["children"]:
                d = {}
                d["bus info"] = "%s@%s" % ( self.device_id, device["logicalname"])
                d["logicalname"] = device["logicalname"]
                d["product"] = device["product"]
                d["serial"] = device["serial"]
                d["version"] = device["version"]
                d["size"] = device["size"]
                d["description"] = device["description"]

                self.disks.append(d)

        elif "nvme" in obj["configuration"]["driver"]:
            d = {}
            d["bus info"] = "%s@%s" % ( self.device_id, obj["businfo"])
            d["vendor"] = obj["vendor"]
            d["version"] = obj["version"]
            d["description"] = obj["description"]
            d["product"] = obj["product"]

            self.disks.append(d)

    def find_cpus(self, obj):
        pprint(obj)
        c = {}
        c["bus info"] = "%s@%s" % ( self.device_id, obj["businfo"])
        c["product"] = obj["product"]
        c["vendor"] = obj["vendor"]
        c["description"] = obj["description"]

        self.cpus.append(c)

    def find_memories(self, obj):
        if "children" not in obj:
            print("not a DIMM memory.")
            return

        for dimm in obj["children"]:
            if "empty" in dimm["description"]:
                continue

            d = {}
            d["bus info"] = "%s@%s" % ( self.device_id, dimm["slot"])
            d["slot"] = dimm["slot"]
            d["description"] = dimm["description"]
            d["id"] = dimm["id"]
            d["serial"] = dimm["serial"]
            d["vendor"] = dimm["vendor"]
            d["product"] = dimm["product"]
            d["size"] = dimm["size"] / 2 ** 20 / 1024

            self.memories.append(d)

    def walk_bridge(self, obj):
        if "children" not in obj:
            return

        for bus in obj["children"]:
            if bus["class"] == "storage":
                self.find_storage(bus)

            if "children" in bus:
                for b in bus["children"]:
                    if b["class"] == "storage":
                        self.find_storage(b)
                    if b["class"] == "network":
                        self.find_network(b)


if  __name__ == "__main__":
    pass
