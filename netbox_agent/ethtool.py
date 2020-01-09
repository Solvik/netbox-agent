import re
from shutil import which
from pprint import pprint
import subprocess

#  Originally from https://github.com/opencoff/useful-scripts/blob/master/linktest.py

#    'Connector':'connector',
#    'Transceiver type': 'transciever_type',

module_map = {
    'Identifier' : 'identifier',
    'Extended identifier': 'extended_identifier',
    'Vendor name': 'vendor',
    'Vendor PN': 'partnumber',
    'Vendor SN': 'serialnumber',
    'Vendor rev': 'revision',
}

# mapping fields from ethtool output to simple names
field_map = {
    'Supported ports': 'ports',
    'Supported link modes': 'sup_link_modes',
    'Supports auto-negotiation': 'sup_autoneg',
    'Advertised link modes':  'adv_link_modes',
    'Advertised auto-negotiation': 'adv_autoneg',
    'Speed': 'speed',
    'Duplex': 'duplex',
    'Port': 'port',
    'Auto-negotiation': 'autoneg',
    'Link detected': 'link',
}


def merge_two_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z


class Ethtool():
    """
    This class aims to parse ethtool output
    There is several bindings to have something proper, but it requires
    compilation and other requirements.
    """
    def __init__(self, interface, *args, **kwargs):
        self.interface = interface

    def _parse_ethtool_output(self):
        """
        parse ethtool output
        """

        output = subprocess.getoutput('sudo /usr/sbin/ethtool {}'.format(self.interface))

        fields = {}
        field = ''
        fields['speed'] = '-'
        fields['link'] = '-'
        fields['duplex'] = '-'
        for line in output.split('\n')[1:]:
            line = line.rstrip()
            r = line.find(':')
            if r > 0:
                field = line[:r].strip()
                if field not in field_map:
                    continue
                field = field_map[field]
                output = line[r+1:].strip()
                fields[field] = output
            else:
                if len(field) > 0 and \
                   field in field_map:
                    fields[field] += ' ' + line.strip()
        return fields

    def _parse_ethtool_info_output(self):
        status, output = subprocess.getstatusoutput('sudo /usr/sbin/ethtool -i {}'.format(self.interface))

        if status != 0:
            return {}

        fields = {}
        field = ''

        for line in output.split('\n'):
            line = line.rstrip()
            r = line.find(':')
            if r > 0:
                field = line[:r].strip()
                output = line[r+1:].strip()
                fields[field] = output

        return fields
         
    def _parse_ethtool_module_output(self):
        """
          ethtool output is a mess..  good for human reading, bad for parsing.
          we massage the output to make it move useful for inventory purposes
          ie, connector and type, plus dropping un needed information.
        """

        status, output = subprocess.getstatusoutput('sudo /usr/sbin/ethtool -m {}'.format(self.interface))
        if status != 0:
            return {}

        fields = {}
        field = ''
        transciever = []

        for line in output.split('\n'):
            line = line.rstrip()
            r = line.find(':')
            if r > 0:
                field = line[:r].strip()
                if 'Identifier' in field:
                    c = re.match(r'.*\((?P<identifier>\w+)\).*', line[r+1:].strip())
                    fields['identifier'] = c.group('identifier')
                    continue
                if 'Connector' in field:
                    c = re.match(r'.*\((?P<connector>\w+)\).*', line[r+1:].strip())
                    fields['connector'] = c.group('connector')
                    continue
                if 'type' in field:
                    field = line[r+1:].strip().replace('10G Ethernet: ', '')
                    field = field.strip().replace('100G Ethernet: ', '')
                    field = field.strip().replace('40G Ethernet: ', '')
                    field = field.strip().replace('Ethernet: ', '')
                    if 'FC:' in field:
                        continue
                    transciever.append(field)
                    continue
                if field not in module_map:
                    continue
                fields[module_map[field]] = line[r+1:].strip()

        j = ", "
        fields['transciever_type'] = j.join(transciever)

        return fields

    def parse(self):
        if which('ethtool') is None:
            return None
        output = self._parse_ethtool_output()
        output.update(self._parse_ethtool_info_output())
        output.update(self._parse_ethtool_module_output())
        return output
