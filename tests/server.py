
import mock
import netifaces

from netbox_agent.config import config
from netbox_agent.config import netbox_instance as nb
from netbox_agent.dmidecode import parse
from netbox_agent.server import ServerBase
from netbox_agent.vendors.hp import HPHost
from tests.conftest import parametrize_with_fixtures
from tests.constants import DEFAULT_DATACENTER
from tests.utils import setup_netbox


@parametrize_with_fixtures('dmidecode/')
def test_init(dmi_fixture):
    dmi = parse(dmi_fixture)
    server = ServerBase(dmi)
    assert server


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'HP_SL4540_Gen8',
        'HP_BL460c_Gen9',
        'HP_DL380p_Gen8',
        'HP_SL4540_Gen8'
    ])
def test_hp_service_tag(dmi_fixture):
    dmi = parse(dmi_fixture)
    server = ServerBase(dmi)
    assert server.get_service_tag() == '4242'


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'unknown.txt'
    ])
def test_generic_host_service_tag(dmi_fixture):
    dmi = parse(dmi_fixture)
    server = ServerBase(dmi)
    assert server.get_service_tag() == '42'


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'unknown.txt'
    ])
def test_generic_host_product_name(dmi_fixture):
    dmi = parse(dmi_fixture)
    server = ServerBase(dmi)
    assert server.get_product_name() == 'SR'


@mock.patch('netifaces.ifaddresses')
@mock.patch('netifaces.interfaces')
@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'HP_SL4540_Gen8',
    ], argname='dmi_fixture')
def test_create_server(
        mock_interfaces,
        mock_ifaddresses,
        fs,
        dmi_fixture,
):
    fake_addresses = {}
    fake_addresses[netifaces.AF_INET] = [{'addr': '42.42.42.42', 'netmask': '255.255.255.0'}]
    fake_addresses[netifaces.AF_LINK] = [{'addr': 'a8:1e:84:f2:9e:69'}]

    mock_interfaces.return_value = ['enp1s0f0']
    mock_ifaddresses.return_value = fake_addresses

    dmi = parse(dmi_fixture)
    server = HPHost(dmi)

    setup_netbox(
        DEFAULT_DATACENTER,
        'Server',
        'HP',
        server.get_product_name(),
    )

    # Create fake /sys/class/net directory with fake interface and MAC addr
    fs.create_file('/tmp/enp1s0f0/address', contents='a8:1e:84:f2:9e:69')
    fs.create_symlink('/sys/class/net/enp1s0f0', '/tmp/enp1s0f0')

    server.netbox_create(config)

    # Check serial tag is correct
    assert server.get_service_tag() == '4242'
    network_card = server.network.get_netbox_network_card({'name': 'enp1s0f0', 'mac': None})

    # Check network card is correct
    assert network_card.name == 'enp1s0f0'

    # Check IP on network card
    ips = nb.ipam.ip_addresses.filter(
        interface_id=network_card.id
    )
    assert ips[0].address == '42.42.42.42/24'
