#  Originally from https://github.com/opencoff/useful-scripts/blob/master/linktest.py

# mapping fields from ethtool output to simple names
field_map = { 'Supported ports': 'ports',
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

def parse_ethtool_output(data):
    """parse ethtool output"""

    fields = {}
    field  = ""
    fields['speed']  = "-"
    fields['link']   = "-"
    fields['duplex'] = '-'
    for line in data.split('\n')[1:]:
        line = line.rstrip()
        r    = line.find(':')
        #verbose("       line=|%s|", line)
        if r > 0:
            field = line[:r].strip()
            if field not in field_map:
                continue
            field = field_map[field]
            data  = line[r+1:].strip()
            fields[field] = data
            #verbose("  %s=%s", field, data)
        else:
            if len(field) > 0 and \
               field in field_map.keys():
                fields[field] +=  ' ' + line.strip()
    return fields
