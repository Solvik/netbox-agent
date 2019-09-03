import logging

from netbox_agent.config import netbox_instance as nb, config

PSU_DMI_TYPE = 39


class PowerSupply():
    def __init__(self, server=None):
        self.server = server
        netbox_server = self.server.get_netbox_server()
        if self.server.is_blade():
            self.device_id = netbox_server.parent_device.id if netbox_server else None
        else:
            self.device_id = netbox_server.id if netbox_server else None

    def get_power_supply(self):
        power_supply = []
        for psu in self.server.dmi.get_by_type(PSU_DMI_TYPE):
            if 'Present' not in psu['Status']:
                continue

            max_power = psu.get('Max Power Capacity').split()[0]
            desc = '{} - {}'.format(
                psu.get('Manufacturer', 'No Manufacturer').strip(),
                psu.get('Name', 'No name').strip(),
            )
            power_supply.append({
                'name': psu.get('Serial Number', 'No S/N').strip(),
                'description': desc,
                'allocated_draw': None,
                'maximum_draw': int(max_power),
                'device': self.device_id,
                })
        return power_supply

    def get_netbox_power_supply(self):
        return nb.dcim.power_ports.filter(
            device_id=self.device_id
            )

    def create_or_update_power_supply(self):
        nb_psus = self.get_netbox_power_supply()
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
