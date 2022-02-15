import logging
import socket
import subprocess
import sys
from pprint import pprint

import netbox_agent.dmidecode as dmidecode
from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.inventory import Inventory
from netbox_agent.location import Datacenter, Rack, Tenant
from netbox_agent.misc import create_netbox_tags, get_device_role, get_device_type
from netbox_agent.network import ServerNetwork
from netbox_agent.power import PowerSupply


class ServerBase():
    def __init__(self, dmi=None):
        if dmi:
            self.dmi = dmi
        else:
            self.dmi = dmidecode.parse()

        self.baseboard = dmidecode.get_by_type(self.dmi, 'Baseboard')
        self.bios = dmidecode.get_by_type(self.dmi, 'BIOS')
        self.chassis = dmidecode.get_by_type(self.dmi, 'Chassis')
        self.system = dmidecode.get_by_type(self.dmi, 'System')
        self.inventory = Inventory(server=self)

        self.network = None

        self.tags = list(set(config.device.tags.split(','))) if config.device.tags else []
        if self.tags and len(self.tags):
            create_netbox_tags(self.tags)

    def get_tenant(self):
        tenant = Tenant()
        return tenant.get()

    def get_netbox_tenant(self):
        tenant = self.get_tenant()
        if tenant is None:
            return None
        nb_tenant = nb.tenancy.tenants.get(
            slug=self.get_tenant()
        )
        return nb_tenant

    def get_datacenter(self):
        dc = Datacenter()
        return dc.get()

    def get_netbox_datacenter(self):
        dc = self.get_datacenter()
        if dc is None:
            logging.error("Specificing a datacenter (Site) is mandatory in Netbox")
            sys.exit(1)

        nb_dc = nb.dcim.sites.get(
            slug=dc,
        )
        if nb_dc is None:
            logging.error("Site (slug: {}) has not been found".format(dc))
            sys.exit(1)

        return nb_dc

    def update_netbox_location(self, server):
        dc = self.get_datacenter()
        nb_rack = self.get_netbox_rack()
        nb_dc = self.get_netbox_datacenter()

        update = False
        if dc and server.site and server.site.slug != nb_dc.slug:
            logging.info('Datacenter location has changed from {} to {}, updating'.format(
                server.site.slug,
                nb_dc.slug,
            ))
            update = True
            server.site = nb_dc.id

        if (
            server.rack
            and nb_rack
            and server.rack.id != nb_rack.id
        ):
            logging.info('Rack location has changed from {} to {}, updating'.format(
                server.rack,
                nb_rack,
            ))
            update = True
            server.rack = nb_rack
            if nb_rack is None:
                server.face = None
                server.position = None
        return update, server

    def update_netbox_expansion_location(self, server, expansion):
        update = False
        if expansion.tenant != server.tenant:
            expansion.tenant = server.tenant
            update = True
        if expansion.site != server.site:
            expansion.site = server.site
            update = True
        if expansion.rack != server.rack:
            expansion.rack = server.rack
            update = True
        return update

    def get_rack(self):
        rack = Rack()
        return rack.get()

    def get_netbox_rack(self):
        rack = self.get_rack()
        datacenter = self.get_netbox_datacenter()
        if not rack:
            return None
        if rack and not datacenter:
            logging.error("Can't get rack if no datacenter is configured or found")
            sys.exit(1)

        return nb.dcim.racks.get(
            name=rack,
            site_id=datacenter.id,
        )

    def get_product_name(self):
        """
        Return the Chassis Name from dmidecode info
        """
        return self.system[0]['Product Name'].strip()

    def get_service_tag(self):
        """
        Return the Service Tag from dmidecode info
        """
        return self.system[0]['Serial Number'].strip()

    def get_expansion_service_tag(self):
        """
        Return the virtual Service Tag from dmidecode info host
        with 'expansion'
        """
        return self.system[0]['Serial Number'].strip() + " expansion"

    def get_hostname(self):
        if config.hostname_cmd is None:
            return '{}'.format(socket.gethostname())
        return subprocess.getoutput(config.hostname_cmd)

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

    def get_power_consumption(self):
        raise NotImplementedError

    def get_expansion_product(self):
        raise NotImplementedError

    def _netbox_create_chassis(self, datacenter, tenant, rack):
        device_type = get_device_type(self.get_chassis())
        device_role = get_device_role(config.device.chassis_role)
        serial = self.get_chassis_service_tag()
        logging.info('Creating chassis blade (serial: {serial})'.format(
            serial=serial))
        new_chassis = nb.dcim.devices.create(
            name=self.get_chassis_name(),
            device_type=device_type.id,
            serial=serial,
            device_role=device_role.id,
            site=datacenter.id if datacenter else None,
            tenant=tenant.id if tenant else None,
            rack=rack.id if rack else None,
            tags=self.tags,
        )
        return new_chassis

    def _netbox_create_blade(self, chassis, datacenter, tenant, rack):
        device_role = get_device_role(config.device.blade_role)
        device_type = get_device_type(self.get_product_name())
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
            tenant=tenant.id if tenant else None,
            rack=rack.id if rack else None,
            tags=self.tags,
        )
        return new_blade

    def _netbox_create_blade_expansion(self, chassis, datacenter, tenant, rack):
        device_role = get_device_role(config.device.blade_role)
        device_type = get_device_type(self.get_expansion_product())
        serial = self.get_expansion_service_tag()
        hostname = self.get_hostname() + " expansion"
        logging.info(
            'Creating expansion (serial: {serial}) {hostname} on chassis {chassis_serial}'.format(
                serial=serial, hostname=hostname, chassis_serial=chassis.serial
            ))
        new_blade = nb.dcim.devices.create(
            name=hostname,
            serial=serial,
            device_role=device_role.id,
            device_type=device_type.id,
            parent_device=chassis.id,
            site=datacenter.id if datacenter else None,
            tenant=tenant.id if tenant else None,
            rack=rack.id if rack else None,
            tags=self.tags,
        )
        return new_blade

    def _netbox_deduplicate_server(self):
        serial = self.get_service_tag()
        hostname = self.get_hostname()
        server = nb.dcim.devices.get(name=hostname)
        if server and server.serial != serial:
            server.delete()

    def _netbox_create_server(self, datacenter, tenant, rack):
        device_role = get_device_role(config.device.server_role)
        device_type = get_device_type(self.get_product_name())
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
            tenant=tenant.id if tenant else None,
            rack=rack.id if rack else None,
            tags=self.tags,
        )
        return new_server

    def get_netbox_server(self, expansion=False):
        if expansion is False:
            return nb.dcim.devices.get(serial=self.get_service_tag())
        else:
            return nb.dcim.devices.get(serial=self.get_expansion_service_tag())

    def _netbox_set_or_update_blade_slot(self, server, chassis, datacenter):
        # before everything check if right chassis
        actual_device_bay = server.parent_device.device_bay if server.parent_device else None
        actual_chassis = actual_device_bay.device if actual_device_bay else None
        slot = self.get_blade_slot()
        if actual_chassis and \
           actual_chassis.serial == chassis.serial and \
           actual_device_bay.name == slot:
            return

        real_device_bays = nb.dcim.device_bays.filter(
            device_id=chassis.id,
            name=slot,
        )
        if len(real_device_bays) > 0:
            logging.info(
                'Setting device ({serial}) new slot on {slot} '
                '(Chassis {chassis_serial})..'.format(
                    serial=server.serial, slot=slot, chassis_serial=chassis.serial
                ))
            # reset actual device bay if set
            if actual_device_bay:
                actual_device_bay.installed_device = None
                actual_device_bay.save()
            # setup new device bay
            real_device_bay = real_device_bays[0]
            real_device_bay.installed_device = server
            real_device_bay.save()
        else:
            logging.error('Could not find slot {slot} for chassis'.format(
                slot=slot
            ))

    def _netbox_set_or_update_blade_expansion_slot(self, expansion, chassis, datacenter):
        # before everything check if right chassis
        actual_device_bay = expansion.parent_device.device_bay if expansion.parent_device else None
        actual_chassis = actual_device_bay.device if actual_device_bay else None
        slot = self.get_blade_expansion_slot()
        if actual_chassis and \
           actual_chassis.serial == chassis.serial and \
           actual_device_bay.name == slot:
            return

        real_device_bays = nb.dcim.device_bays.filter(
            device_id=chassis.id,
            name=slot,
        )
        if len(real_device_bays) == 0:
            logging.error('Could not find slot {slot} expansion for chassis'.format(
                slot=slot
            ))
            return
        logging.info(
            'Setting device expansion ({serial}) new slot on {slot} '
            '(Chassis {chassis_serial})..'.format(
                serial=expansion.serial, slot=slot, chassis_serial=chassis.serial
            ))
        # reset actual device bay if set
        if actual_device_bay:
            actual_device_bay.installed_device = None
            actual_device_bay.save()
        # setup new device bay
        real_device_bay = real_device_bays[0]
        real_device_bay.installed_device = expansion
        real_device_bay.save()

    def netbox_create_or_update(self, config):
        """
        Netbox method to create or update info about our server/blade

        Handle:
        * new chassis for a blade
        * new slot for a blade
        * hostname update
        * Network infos
        * Inventory management
        * PSU management
        """
        datacenter = self.get_netbox_datacenter()
        rack = self.get_netbox_rack()
        tenant = self.get_netbox_tenant()

        if config.purge_old_devices:
            self._netbox_deduplicate_server()

        if self.is_blade():
            chassis = nb.dcim.devices.get(
                serial=self.get_chassis_service_tag()
            )
            # Chassis does not exist
            if not chassis:
                chassis = self._netbox_create_chassis(datacenter, tenant, rack)

            server = nb.dcim.devices.get(serial=self.get_service_tag())
            if not server:
                server = self._netbox_create_blade(chassis, datacenter, tenant, rack)

            # Set slot for blade
            self._netbox_set_or_update_blade_slot(server, chassis, datacenter)
        else:
            server = nb.dcim.devices.get(serial=self.get_service_tag())
            if not server:
                server = self._netbox_create_server(datacenter, tenant, rack)

        logging.debug('Updating Server...')
        # check network cards
        if config.register or config.update_all or config.update_network:
            self.network = ServerNetwork(server=self)
            self.network.create_or_update_netbox_network_cards()
        update_inventory = config.inventory and (config.register or
                config.update_all or config.update_inventory)
        # update inventory if feature is enabled
        if update_inventory:
            self.inventory.create_or_update()
        # update psu
        if config.register or config.update_all or config.update_psu:
            self.power = PowerSupply(server=self)
            self.power.create_or_update_power_supply()
            self.power.report_power_consumption()

        expansion = nb.dcim.devices.get(serial=self.get_expansion_service_tag())
        if self.own_expansion_slot() and config.expansion_as_device:
            logging.debug('Update Server expansion...')
            if not expansion:
                expansion = self._netbox_create_blade_expansion(chassis, datacenter, tenant, rack)

            # set slot for blade expansion
            self._netbox_set_or_update_blade_expansion_slot(expansion, chassis, datacenter)
            if update_inventory:
                # Updates expansion inventory
                inventory = Inventory(server=self, update_expansion=True)
                inventory.create_or_update()
        elif self.own_expansion_slot() and expansion:
            expansion.delete()
            expansion = None

        update = 0
        # for every other specs
        # check hostname
        if server.name != self.get_hostname():
            update += 1
            server.name = self.get_hostname()


        if sorted(set(server.tags)) != sorted(set(self.tags)):
            server.tags = self.tags
            update += 1

        if config.update_all or config.update_location:
            ret, server = self.update_netbox_location(server)
            update += ret

        if update:
            server.save()

        if expansion:
            update = 0
            expansion_name = server.name + ' expansion'
            if expansion.name != expansion_name:
                expansion.name = expansion_name
                update += 1
            if self.update_netbox_expansion_location(server, expansion):
                update += 1
            if update:
                expansion.save()
        logging.debug('Finished updating Server!')

    def print_debug(self):
        self.network = ServerNetwork(server=self)
        print('Datacenter:', self.get_datacenter())
        print('Netbox Datacenter:', self.get_netbox_datacenter())
        print('Rack:', self.get_rack())
        print('Netbox Rack:', self.get_netbox_rack())
        print('Is blade:', self.is_blade())
        print('Got expansion:', self.own_expansion_slot())
        print('Product Name:', self.get_product_name())
        print('Chassis:', self.get_chassis())
        print('Chassis service tag:', self.get_chassis_service_tag())
        print('Service tag:', self.get_service_tag())
        print('NIC:',)
        pprint(self.network.get_network_cards())
        pass
