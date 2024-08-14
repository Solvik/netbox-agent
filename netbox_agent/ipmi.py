import logging
import subprocess

from netaddr import IPNetwork


class IPMI():
    """
    Parse IPMI output
    ie:

    Set in Progress         : Set Complete
    Auth Type Support       :
    Auth Type Enable        : Callback :
                            : User     :
                            : Operator :
                            : Admin    :
                            : OEM      :
    IP Address Source       : DHCP Address
    IP Address              : 10.192.2.1
    Subnet Mask             : 255.255.240.0
    MAC Address             : 98:f2:b3:f0:ee:1e
    SNMP Community String   :
    BMC ARP Control         : ARP Responses Enabled, Gratuitous ARP Disabled
    Default Gateway IP      : 10.192.2.254
    802.1q VLAN ID          : Disabled
    802.1q VLAN Priority    : 0
    RMCP+ Cipher Suites     : 0,1,2,3
    Cipher Suite Priv Max   : XuuaXXXXXXXXXXX
                            :     X=Cipher Suite Unused
                            :     c=CALLBACK
                            :     u=USER
                            :     o=OPERATOR
                            :     a=ADMIN
                            :     O=OEM
    Bad Password Threshold  : Not Available
    """

    def __init__(self):
        self.ret, self.output = subprocess.getstatusoutput('ipmitool lan print')
        if self.ret != 0:
            if self.output != "":
                self.ret = 0
            logging.error('Failure when getting ipmi info: {}'.format(self.output))

    def parse(self):
        _ipmi = {}
        if self.ret != 0:
            return _ipmi

        for line in self.output.splitlines():
            key = line.split(':')[0].strip()
            if key not in ['802.1q VLAN ID', 'IP Address', 'Subnet Mask', 'MAC Address']:
                continue
            value = ':'.join(line.split(':')[1:]).strip()
            _ipmi[key] = value

        if not _ipmi:
            return _ipmi

        ret = {}
        ret['name'] = 'IPMI'
        ret["mtu"] = 1500
        ret['bonding'] = False
        ret['mac'] = _ipmi['MAC Address']
        ip = _ipmi['IP Address']
        netmask = _ipmi['Subnet Mask']
        if '802.1q VLAN ID' in _ipmi and _ipmi['802.1q VLAN ID'] != 'Disabled':
            ret['vlan'] = int(_ipmi['802.1q VLAN ID'])
        else:
            ret['vlan'] = None
        address = str(IPNetwork(f'{ip}/{netmask}'))

        ret['ip'] = [address]
        ret['ipmi'] = True
        return ret
