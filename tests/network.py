from types import SimpleNamespace
from unittest.mock import MagicMock

from netbox_agent.lldp import LLDP
from netbox_agent.network import Network
from tests.conftest import parametrize_with_fixtures


@parametrize_with_fixtures(
    "lldp/",
    only_filenames=[
        "dedibox1.txt",
    ],
)
def test_lldp_parse_with_port_desc(fixture):
    lldp = LLDP(fixture)
    assert lldp.get_switch_port("enp1s0f0") == "RJ-9"


@parametrize_with_fixtures(
    "lldp/",
    only_filenames=[
        "qfx.txt",
    ],
)
def test_lldp_parse_without_ifname(fixture):
    lldp = LLDP(fixture)
    assert lldp.get_switch_port("eth0") == "xe-0/0/1"


@parametrize_with_fixtures(
    "lldp/",
    only_filenames=[
        "223.txt",
    ],
)
def test_lldp_parse_with_vlan(fixture):
    lldp = LLDP(fixture)
    assert lldp.get_switch_vlan("eth0") == {"300": {"pvid": True}}
    assert lldp.get_switch_vlan("eth1") == {"300": {}}


def test_set_netbox_interface_primary_mac_scopes_lookup_to_interface():
    network = object.__new__(Network)
    network.nb_net = SimpleNamespace(mac_addresses=MagicMock())
    network.nb_net.mac_addresses.get.return_value = SimpleNamespace(id=123)
    interface = SimpleNamespace(id=456, primary_mac_address=None)

    network.set_netbox_interface_primary_mac(interface, "AA:BB:CC:DD:EE:FF")

    network.nb_net.mac_addresses.get.assert_called_once_with(
        interface_id=456,
        mac_address="AA:BB:CC:DD:EE:FF",
    )
    assert interface.primary_mac_address == 123
