from netbox_agent.dmidecode import parse
from netbox_agent.server import ServerBase
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
        'HP_SL4540_Gen8'])
def test_hp_service_tag(fixture):
    dmi = parse(fixture)
    server = ServerBase(dmi)
    assert server.get_service_tag() == '4242'
