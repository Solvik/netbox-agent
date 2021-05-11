import logging

import netbox_agent.dmidecode as dmidecode
from netbox_agent.config import netbox_instance as nb

PSU_DMI_TYPE = 39


class PowerSupply():
    def __init__(self, server=None):
        self.server = server
        self.netbox_server = self.server.get_netbox_server()
        if self.server.is_blade():
            self.device_id = self.netbox_server.parent_device.id if self.netbox_server else None
        else:
            self.device_id = self.netbox_server.id if self.netbox_server else None

    def get_power_supply(self):
        power_supply = []
        for psu in dmidecode.get_by_type(self.server.dmi, PSU_DMI_TYPE):
            if 'Present' not in psu['Status'] or psu['Status'] == 'Not Present':
                continue

            try:
                max_power = int(psu.get('Max Power Capacity').split()[0])
            except ValueError:
                max_power = None
            desc = '{} - {}'.format(
                psu.get('Manufacturer', 'No Manufacturer').strip(),
                psu.get('Name', 'No name').strip(),
            )

            sn = psu.get('Serial Number', '').strip()
            # Let's assume that if no serial and no power reported we skip it
            if sn == '' and max_power is None:
                continue
            if sn == '':
                sn = 'N/A'
            power_supply.append({
                'name': sn,
                'description': desc,
                'allocated_draw': None,
                'maximum_draw': max_power,
                'device': self.device_id,
            })
        return power_supply

    def get_netbox_power_supply(self):
        return nb.dcim.power_ports.filter(
            device_id=self.device_id
        )

    def create_or_update_power_supply(self):
        nb_psus = list(self.get_netbox_power_supply())
        psus = self.get_power_supply()

        # Delete unknown PSU
        delete = False
        for nb_psu in nb_psus:
            if nb_psu.name not in [x['name'] for x in psus]:
                logging.info('Deleting unknown locally PSU {name}'.format(
                    name=nb_psu.name
                ))
                nb_psu.delete()
                delete = True

        if delete:
            nb_psus = self.get_netbox_power_supply()

        # sync existing Netbox PSU with local infos
        for nb_psu in nb_psus:
            local_psu = next(
                item for item in psus if item['name'] == nb_psu.name
            )
            update = False
            if nb_psu.description != local_psu['description']:
                update = True
                nb_psu.description = local_psu['description']
            if nb_psu.maximum_draw != local_psu['maximum_draw']:
                update = True
                nb_psu.maximum_draw = local_psu['maximum_draw']
            if update:
                nb_psu.save()

        for psu in psus:
            if psu['name'] not in [x.name for x in nb_psus]:
                logging.info('Creating PSU {name} ({description}), {maximum_draw}W'.format(
                    **psu
                ))
                nb_psu = nb.dcim.power_ports.create(
                    **psu
                )

        return True

    def report_power_consumption(self):
        try:
            psu_cons = self.server.get_power_consumption()
        except NotImplementedError:
            logging.error('Cannot report power consumption for this vendor')
            return False
        nb_psus = self.get_netbox_power_supply()

        if not len(nb_psus) or not len(psu_cons):
            return False

        # find power feeds for rack or dc
        voltage = None
        pwr_feeds = None
        if self.netbox_server.rack:
            pwr_feeds = nb.dcim.power_feeds.filter(
                rack=self.netbox_server.rack.id
            )
        if pwr_feeds is None or not len(pwr_feeds):
            logging.info('Could not find power feeds for Rack, defaulting value to 230')
            voltage = 230

        for i, nb_psu in enumerate(nb_psus):
            nb_psu.allocated_draw = float(psu_cons[i]) * voltage
            if nb_psu.allocated_draw < 1:
                logging.info('PSU is not connected or in standby mode')
                continue
            nb_psu.save()
            logging.info('Updated power consumption for PSU {}: {}W'.format(
                nb_psu.name,
                nb_psu.allocated_draw,
            ))

        return True
