import logging
import subprocess


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
            logging.error('Cannot get ipmi info: {}'.format(self.output))

    def parse(self):
        ret = {}
        if self.ret != 0:
            return ret
        for line in self.output.splitlines():
            key = line.split(':')[0].strip()
            value = ':'.join(line.split(':')[1:]).strip()
            ret[key] = value
        return ret
