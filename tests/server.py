from netbox_agent.dmidecode import parse
from netbox_agent.server import ServerBase
from netbox_agent.vendors.hp import HPHost
from netbox_agent.vendors.qct import QCTHost
from netbox_agent.vendors.supermicro import SupermicroHost
from tests.conftest import parametrize_with_fixtures


@parametrize_with_fixtures('dmidecode/')
def test_init(fixture):
    dmi = parse(fixture)
    server = ServerBase(dmi)
    assert server


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'HP_SL4540_Gen8',
        'HP_BL460c_Gen9',
        'HP_DL380p_Gen8',
        'HP_SL4540_Gen8'
        'HP_ProLiant_BL460c_Gen10_Graphics_Exp'
    ])
def test_hp_service_tag(fixture):
    dmi = parse(fixture)
    server = HPHost(dmi)
    assert server.get_service_tag() == '4242'


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'HP_ProLiant_m710x'
    ])
def test_moonshot_blade(fixture):
    dmi = parse(fixture)
    server = HPHost(dmi)
    assert server.get_service_tag() == 'CN66480BLA'
    assert server.get_chassis_service_tag() == 'CZ3702MD5K'
    assert server.is_blade() is True
    assert server.own_expansion_slot() is False


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'SYS-5039MS-H12TRF-OS012.txt'
    ])
def test_supermicro_blade(fixture):
    dmi = parse(fixture)
    server = SupermicroHost(dmi)
    assert server.get_service_tag() == 'E235735X6B01665'
    assert server.get_chassis_service_tag() == 'C9390AF40A20098'
    assert server.get_chassis() == 'SYS-5039MS-H12TRF-OS012'
    assert server.is_blade() is True


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'SM_SYS-6018R'
    ])
def test_supermicro_pizza(fixture):
    dmi = parse(fixture)
    server = SupermicroHost(dmi)
    assert server.get_service_tag() == 'A177950X7709591'
    assert server.get_chassis() == 'SYS-6018R-TDTPR'
    assert server.is_blade() is False


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'QCT_X10E-9N'
    ])
def test_qct_x10(fixture):
    dmi = parse(fixture)
    server = QCTHost(dmi)
    assert server.get_service_tag() == 'QTFCQ57140285'


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'unknown.txt'
    ])
def test_generic_host_service_tag(fixture):
    dmi = parse(fixture)
    server = ServerBase(dmi)
    assert server.get_service_tag() == '42'


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'unknown.txt'
    ])
def test_generic_host_product_name(fixture):
    dmi = parse(fixture)
    server = ServerBase(dmi)
    assert server.get_product_name() == 'SR'


@parametrize_with_fixtures(
    'dmidecode/', only_filenames=[
        'HP_ProLiant_BL460c_Gen10_Graphics_Exp'
    ])
def test_hp_blade_with_gpu_expansion(fixture):
    dmi = parse(fixture)
    server = HPHost(dmi)
    assert server.get_service_tag() == '4242'
    assert server.get_chassis_service_tag() == '4343'
    assert server.is_blade() is True
    assert server.own_expansion_slot() is True
    assert server.get_expansion_service_tag() == '4242 expansion'
