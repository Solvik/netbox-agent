from netbox_agent.lldp import LLDP
from netbox_agent.network import get_vlan_id
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


def test_get_vlan_id_from_kernel_vlan_info(tmp_path):
    (tmp_path / "p6p3.vlan9").write_text("p6p3.vlan9  VID: 9       REORDER_HDR: 1\n")
    assert get_vlan_id("p6p3.vlan9", tmp_path) == 9


def test_get_vlan_id_from_numeric_suffix(tmp_path):
    assert get_vlan_id("eth0.9", tmp_path) == 9
    assert get_vlan_id("eno1.50", tmp_path) == 50
    assert get_vlan_id("eth0.9.extra", tmp_path) == 9


def test_get_vlan_id_from_non_numeric_dotted_name(tmp_path):
    assert get_vlan_id("foo.bar", tmp_path) is None


def test_get_vlan_id_with_unusable_kernel_data(tmp_path):
    (tmp_path / "eth0.9").write_text("unexpected content\n")
    (tmp_path / "p6p3.vlan9").write_text("unexpected content\n")
    assert get_vlan_id("eth0.9", tmp_path) == 9
    assert get_vlan_id("p6p3.vlan9", tmp_path) is None
