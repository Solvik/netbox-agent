from netbox_agent.lldp import LLDP
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
