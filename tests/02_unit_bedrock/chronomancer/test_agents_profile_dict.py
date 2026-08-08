from types import SimpleNamespace

from src2.interfaces.telegram.chronomancer.agents import (
    _pillar_to_dict_helper,
    _profile_to_dict,
    _session_to_profile,
    _unwrap_profile_obj,
)


def test_unwrap_profile_obj():
    p = SimpleNamespace(gender='M', alias='TestUser')
    session = SimpleNamespace(profile=p)
    assert _unwrap_profile_obj(session) == p
    assert _unwrap_profile_obj(p) == p


def test_pillar_to_dict_helper():
    pil = SimpleNamespace(stem='Bing', branch='Wu')
    assert _pillar_to_dict_helper(pil) == {'stem': 'Bing', 'branch': 'Wu'}
    assert _pillar_to_dict_helper({'stem': 'Jia', 'branch': 'Zi'}) == {'stem': 'Jia', 'branch': 'Zi'}
    assert _pillar_to_dict_helper(None) == {}


def test_profile_to_dict_with_session():
    pil = SimpleNamespace(stem='Bing', branch='Wu')
    p = SimpleNamespace(gender='M', alias='TestUser', year_pillar=pil)
    session = SimpleNamespace(profile=p)
    res = _session_to_profile(session)
    assert res['gender'] == 'M'
    assert res['alias'] == 'TestUser'
    assert res['year_pillar'] == {'stem': 'Bing', 'branch': 'Wu'}


def test_profile_to_dict_with_dict():
    d = {'gender': 'F', 'alias': 'DictUser'}
    assert _profile_to_dict(d) == d
