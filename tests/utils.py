
import pynetbox

from netbox_agent.config import netbox_instance as nb


def setup_netbox(dc, device_role, manufacturer, model):
    try:
        nb_dc = nb.dcim.sites.create(
            name=dc,
            slug=dc.lower(),
        )
    except pynetbox.RequestError:
        nb_dc = nb.dcim.sites.get(
            slug=dc.lower()
        )

    try:
        nb_manufacturer = nb.dcim.manufacturers.create(
            name=manufacturer,
            slug=manufacturer.lower(),
        )
    except pynetbox.RequestError:
        nb_manufacturer = nb.dcim.manufacturers.get(
            slug=manufacturer.lower()
        )

    try:
        nb_device_role = nb.dcim.device_roles.create(
            name=device_role,
            slug=device_role.lower(),
            color='f44336',
        )
    except pynetbox.RequestError:
        nb_device_role = nb.dcim.device_roles.get(
            slug=device_role.lower(),
        )

    try:
        nb_device_type = nb.dcim.device_types.create(
            model=model,
            slug=model.lower().replace(' ', '_'),
            device_role=nb_device_role.id,
            manufacturer=nb_manufacturer.id,
        )
    except pynetbox.RequestError:
        nb_device_type = nb.dcim.device_types.get(
            slug=model.lower().replace(' ', '_'),
        )

    return nb_dc, nb_manufacturer, nb_device_role, nb_device_type
