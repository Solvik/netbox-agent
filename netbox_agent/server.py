import logging
from pprint import pprint
import socket

from netbox_agent.config import netbox_instance as nb
import netbox_agent.dmidecode as dmidecode
from netbox_agent.location import Datacenter, Rack
from netbox_agent.network import Network


class ServerBase():
    def __init__(self, dmi=None):
        if dmi:
            self.dmi = dmi
        else:
            self.dmi = dmidecode.parse()
        self.system = self.dmi.get_by_type('System')
        self.bios = self.dmi.get_by_type('BIOS')

        self.network = Network(server=self)

    def get_datacenter(self):
        dc = Datacenter()
        return dc.get()

    def get_netbox_datacenter(self):
        datacenter = nb.dcim.sites.get(
            slug=self.get_datacenter()
        )
        return datacenter

    def get_rack(self):
        rack = Rack()
        return rack.get()

    def get_netbox_rack(self):
        rack = nb.dcim.racks.get(
            name=self.get_rack(),
            datacenter=self.get_netbox_datacenter(),
        )
        return rack

    def get_product_name(self):
        """
        Return the Chassis Name from dmidecode info
        """
        return self.system[0]['Product Name']

    def get_service_tag(self):
        """
        Return the Service Tag from dmidecode info
        """
        return self.system[0]['Serial Number']

    def get_hostname(self):
        return '{}'.format(socket.gethostname())

    def is_blade(self):
        raise NotImplementedError

    def get_blade_slot(self):
        raise NotImplementedError

    def get_chassis(self):
        raise NotImplementedError

    def get_chassis_name(self):
        raise NotImplementedError

    def get_chassis_service_tag(self):
        raise NotImplementedError

    def get_bios_version(self):
        raise NotImplementedError

    def get_bios_version_attr(self):
        raise NotImplementedError

    def get_bios_release_date(self):
        raise NotImplementedError

    def _netbox_create_blade_chassis(self, datacenter):
        device_type = nb.dcim.device_types.get(
            model=self.get_chassis(),
        )
        if not device_type:
            error_msg = 'Chassis "{}" doesn\'t exist'.format(self.get_chassis())
            logging.error(error_msg)
            raise Exception(error_msg)
        device_role = nb.dcim.device_roles.get(
            name='Server Chassis',
        )
        serial = self.get_chassis_service_tag()
        logging.info('Creating chassis blade (serial: {serial})'.format(
            serial=serial))
        new_chassis = nb.dcim.devices.create(
            name=self.get_chassis_name(),
            device_type=device_type.id,
            serial=serial,
            device_role=device_role.id,
            site=datacenter.id if datacenter else None,
        )
        return new_chassis

    def _netbox_create_blade(self, chassis, datacenter):
        device_role = nb.dcim.device_roles.get(
            name='Blade',
        )
        device_type = nb.dcim.device_types.get(
            model=self.get_product_name(),
        )
        serial = self.get_service_tag()
        hostname = self.get_hostname()
        logging.info(
            'Creating blade (serial: {serial}) {hostname} on chassis {chassis_serial}'.format(
                serial=serial, hostname=hostname, chassis_serial=chassis.serial
            ))
        new_blade = nb.dcim.devices.create(
            name=hostname,
            serial=serial,
            device_role=device_role.id,
            device_type=device_type.id,
            parent_device=chassis.id,
            site=datacenter.id if datacenter else None,
        )
        return new_blade

    def _netbox_set_blade_slot(self, chassis, server):
        slot = self.get_blade_slot()
        # Find the slot and update it with our blade
        device_bays = nb.dcim.device_bays.filter(
            device_id=chassis.id,
            name=slot,
        )
        if len(device_bays) > 0:
            logging.info(
                'Setting device ({serial}) new slot on {slot} '
                '(Chassis {chassis_serial})..'.format(
                    serial=server.serial, slot=slot, chassis_serial=chassis.serial
                ))
            device_bay = device_bays[0]
            device_bay.installed_device = server
            device_bay.save()
        else:
            logging.error('Could not find slot {slot} for chassis'.format(
                slot=slot
            ))

    def _netbox_create_server(self, datacenter):
        device_role = nb.dcim.device_roles.get(
            name='Server',
        )
        device_type = nb.dcim.device_types.get(
            model=self.get_product_name(),
        )
        if not device_type:
            raise Exception('Chassis "{}" doesn\'t exist'.format(self.get_chassis()))
        serial = self.get_service_tag()
        hostname = self.get_hostname()
        logging.info('Creating server (serial: {serial}) {hostname}'.format(
            serial=serial, hostname=hostname))
        new_server = nb.dcim.devices.create(
            name=hostname,
            serial=serial,
            device_role=device_role.id,
            device_type=device_type.id,
            site=datacenter.id if datacenter else None,
        )
        return new_server

    def get_netbox_server(self):
        return nb.dcim.devices.get(serial=self.get_service_tag())

    def netbox_create(self):
        logging.debug('Creating Server..')
        datacenter = self.get_netbox_datacenter()
        if self.is_blade():
            # let's find the blade
            serial = self.get_service_tag()
            blade = nb.dcim.devices.get(serial=serial)
            chassis = nb.dcim.devices.get(serial=self.get_chassis_service_tag())
            # if it doesn't exist, create it
            if not blade:
                # check if the chassis exist before
                # if it doesn't exist, create it
                chassis = nb.dcim.devices.get(
                    serial=self.get_chassis_service_tag()
                    )
                if not chassis:
                    chassis = self._netbox_create_blade_chassis(datacenter)

                blade = self._netbox_create_blade(chassis, datacenter)

            # Set slot for blade
            self._netbox_set_blade_slot(chassis, blade)
        else:
            server = nb.dcim.devices.get(serial=self.get_service_tag())
            if not server:
                self._netbox_create_server(datacenter)

        self.network.create_netbox_network_cards()
        logging.debug('Server created!')

    def _netbox_update_chassis_for_blade(self, server, datacenter):
        chassis = server.parent_device.device_bay.device
        device_bay = nb.dcim.device_bays.get(
            server.parent_device.device_bay.id
        )
        netbox_chassis_serial = server.parent_device.device_bay.device.serial
        move_device_bay = False

        # check chassis serial with dmidecode
        if netbox_chassis_serial != self.get_chassis_service_tag():
            move_device_bay = True
            # try to find the new netbox chassis
            chassis = nb.dcim.devices.get(
                serial=self.get_chassis_service_tag()
            )
            if not chassis:
                chassis = self._netbox_create_blade_chassis(datacenter)
        if move_device_bay or device_bay.name != self.get_blade_slot():
            logging.info('Device ({serial}) seems to have moved, reseting old slot..'.format(
                serial=server.serial))
            device_bay.installed_device = None
            device_bay.save()

            # Set slot for blade
            self._netbox_set_blade_slot(chassis, server)

    def netbox_update(self):
        """
        Netbox method to update info about our server/blade

        Handle:
        * new chasis for a blade
        * new slot for a bblade
        * hostname update
        * new network infos
        """
        logging.debug('Updating Server...')
        server = nb.dcim.devices.get(serial=self.get_service_tag())
        if not server:
            raise Exception("The server (Serial: {}) isn't yet registered in Netbox, register"
                            'it before updating it'.format(self.get_service_tag()))
        update = False
        if self.is_blade():
            datacenter = self.get_netbox_datacenter()
            # if it's already linked to a chassis
            if server.parent_device:
                self._netbox_update_chassis_for_blade(server, datacenter)
            else:
                logging.info('Blade is not in a chassis, fixing...')
                chassis = nb.dcim.devices.get(
                    serial=self.get_chassis_service_tag()
                )
                if not chassis:
                    chassis = self._netbox_create_blade_chassis(datacenter)
                # Set slot for blade
                self._netbox_set_blade_slot(chassis, server)

        # for every other specs
        # check hostname
        if server.name != self.get_hostname():
            update = True
            server.hostname = self.get_hostname()
        # check network cards
        self.network.update_netbox_network_cards()
        if update:
            server.save()
        logging.debug('Finished updating Server!')

    def print_debug(self):
        # FIXME: do something more generic by looping on every get_* methods
        print('Datacenter:', self.get_datacenter())
        print('Netbox Datacenter:', self.get_netbox_datacenter())
        print('Rack:', self.get_rack())
        print('Netbox Rack:', self.get_netbox_rack())
        print('Is blade:', self.is_blade())
        print('Product Name:', self.get_product_name())
        print('Chassis:', self.get_chassis())
        print('Chassis service tag:', self.get_chassis_service_tag())
        print('Service tag:', self.get_service_tag())
        print('NIC:',)
        pprint(self.network.get_network_cards())
        pass
