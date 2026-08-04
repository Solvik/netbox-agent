from netbox_agent.ifconfig import Ifconfig
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


@parametrize_with_fixtures(
    "ifconfig/",
    only_filenames=[
        "freebsd_carp.txt",
    ],
)
def test_ifconfig_parse_freebsd(fixture):
    interfaces = Ifconfig(fixture).interfaces
    # MAC + MTU are picked up from the ether/header lines
    assert interfaces["vtnet0"]["mac"] == "bc:24:11:6e:21:cd"
    assert interfaces["vtnet0"]["mtu"] == 1500
    assert interfaces["vtnet1"]["mac"] == "bc:24:11:90:23:4d"
    assert interfaces["vtnet1"]["mtu"] == 1500
    # interfaces without an ether line have no MAC, but still an MTU
    assert interfaces["lo0"]["mac"] is None
    assert interfaces["lo0"]["mtu"] == 16384
    assert interfaces["pflog0"]["mtu"] == 33152
    assert interfaces["tailscale0"]["mtu"] == 1280
