import logging
import re as _re
import subprocess as _subprocess
import sys

from netbox_agent.misc import is_tool

_handle_re = _re.compile("^Handle\\s+(.+),\\s+DMI\\s+type\\s+(\\d+),\\s+(\\d+)\\s+bytes$")
_in_block_re = _re.compile("^\\t\\t(.+)$")
_record_re = _re.compile("\\t(.+):\\s+(.+)$")
_record2_re = _re.compile("\\t(.+):$")

_type2str = {
    0: "BIOS",
    1: "System",
    2: "Baseboard",
    3: "Chassis",
    4: "Processor",
    5: "Memory Controller",
    6: "Memory Module",
    7: "Cache",
    8: "Port Connector",
    9: "System Slots",
    10: " On Board Devices",
    11: " OEM Strings",
    12: " System Configuration Options",
    13: " BIOS Language",
    14: " Group Associations",
    15: " System Event Log",
    16: " Physical Memory Array",
    17: " Memory Device",
    18: " 32-bit Memory Error",
    19: " Memory Array Mapped Address",
    20: " Memory Device Mapped Address",
    21: " Built-in Pointing Device",
    22: " Portable Battery",
    23: " System Reset",
    24: " Hardware Security",
    25: " System Power Controls",
    26: " Voltage Probe",
    27: " Cooling Device",
    28: " Temperature Probe",
    29: " Electrical Current Probe",
    30: " Out-of-band Remote Access",
    31: " Boot Integrity Services",
    32: " System Boot",
    33: " 64-bit Memory Error",
    34: " Management Device",
    35: " Management Device Component",
    36: " Management Device Threshold Data",
    37: " Memory Channel",
    38: " IPMI Device",
    39: " Power Supply",
    40: " Additional Information",
    41: " Onboard Devices Extended Information",
    42: " Management Controller Host Interface",
}
_str2type = {}
for type_id, type_str in _type2str.items():
    _str2type[type_str] = type_id


def parse(output=None):
    """
    parse the full output of the dmidecode
    command and return a dic containing the parsed information
    """
    if output:
        buffer = output
    else:
        buffer = _execute_cmd()
    if isinstance(buffer, bytes):
        buffer = buffer.decode("utf-8")
    _data = _parse(buffer)
    return _data


def get_by_type(data, type_id):
    """
    filter the output of dmidecode per type
    0   BIOS
    1   System
    2   Baseboard
    3   Chassis
    4   Processor
    5   Memory Controller
    6   Memory Module
    7   Cache
    8   Port Connector
    9   System Slots
    10   On Board Devices
    11   OEM Strings
    12   System Configuration Options
    13   BIOS Language
    14   Group Associations
    15   System Event Log
    16   Physical Memory Array
    17   Memory Device
    18   32-bit Memory Error
    19   Memory Array Mapped Address
    20   Memory Device Mapped Address
    21   Built-in Pointing Device
    22   Portable Battery
    23   System Reset
    24   Hardware Security
    25   System Power Controls
    26   Voltage Probe
    27   Cooling Device
    28   Temperature Probe
    29   Electrical Current Probe
    30   Out-of-band Remote Access
    31   Boot Integrity Services
    32   System Boot
    33   64-bit Memory Error
    34   Management Device
    35   Management Device Component
    36   Management Device Threshold Data
    37   Memory Channel
    38   IPMI Device
    39   Power Supply
    40   Additional Information
    41   Onboard Devices Extended Information
    42   Management Controller Host Interface
    """
    if isinstance(type_id, str):
        type_id = _str2type.get(type_id)
        if type_id is None:
            return None

    result = []
    for entry in data.values():
        if entry["DMIType"] == type_id:
            result.append(entry)

    return result


def _execute_cmd():
    if not is_tool("dmidecode"):
        logging.error(
            "Dmidecode does not seem to be present on your system. Add it your path or "
            "check the compatibility of this project with your distro."
        )
        sys.exit(1)
    return _subprocess.check_output(
        [
            "dmidecode",
        ],
        stderr=_subprocess.PIPE,
    )


def _parse(buffer):
    output_data = {}
    #  Each record is separated by double newlines
    split_output = buffer.split("\n\n")

    for record in split_output:
        record_element = record.splitlines()

        #  Entries with less than 3 lines are incomplete / inactive; skip them
        if len(record_element) < 3:
            continue

        handle_data = _handle_re.findall(record_element[0])

        if not handle_data:
            continue
        handle_data = handle_data[0]

        dmi_handle = handle_data[0]

        output_data[dmi_handle] = {}
        output_data[dmi_handle]["DMIType"] = int(handle_data[1])
        output_data[dmi_handle]["DMISize"] = int(handle_data[2])

        #  Okay, we know 2nd line == name
        output_data[dmi_handle]["DMIName"] = record_element[1]

        in_block_elemet = ""
        in_block_list = ""

        #  Loop over the rest of the record, gathering values
        for i in range(2, len(record_element), 1):
            if i >= len(record_element):
                break
            #  Check whether we are inside a \t\t block
            if in_block_elemet != "":
                in_block_data = _in_block_re.findall(record_element[i])

                if in_block_data:
                    if not in_block_list:
                        in_block_list = [in_block_data[0]]
                    else:
                        in_block_list.append(in_block_data[0])

                    output_data[dmi_handle][in_block_elemet] = in_block_list
                    continue
                else:
                    # We are out of the \t\t block; reset it again, and let
                    # the parsing continue
                    in_block_elemet = ""

            record_data = _record_re.findall(record_element[i])

            #  Is this the line containing handle identifier, type, size?
            if record_data:
                output_data[dmi_handle][record_data[0][0]] = record_data[0][1]
                continue

            #  Didn't findall regular entry, maybe an array of data?

            record_data2 = _record2_re.findall(record_element[i])
            if record_data2:
                #  This is an array of data - let the loop know we are inside
                #  an array block
                in_block_elemet = record_data2[0]
                in_block_list = ""

                continue

    if not output_data:
        raise ParseError("Unable to parse 'dmidecode' output")

    return output_data


class ParseError(Exception):
    pass
