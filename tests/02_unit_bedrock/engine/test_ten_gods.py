"""
Unit tests for Module 6 (Ten Gods).
"""

from src.engine.module6_ten_gods import calculate_ten_gods


def test_calculate_ten_gods_jia():
    dm = "Jia"
    stems = {"pos1": "Jia", "pos2": "Yi", "pos3": "Geng", "pos4": "Xin"}
    res = calculate_ten_gods(dm, stems)
    profile = res["ten_gods_profile"]

    assert profile["pos1"]["ten_god"] == "Bi Jian"
    assert profile["pos2"]["ten_god"] == "Jie Cai"
    assert profile["pos3"]["ten_god"] == "Qi Sha"
    assert profile["pos4"]["ten_god"] == "Zheng Guan"

def test_calculate_ten_gods_bing():
    dm = "Bing"
    stems = {"pos1": "Bing", "pos2": "Ding", "pos3": "Ren", "pos4": "Gui"}
    res = calculate_ten_gods(dm, stems)
    profile = res["ten_gods_profile"]

    assert profile["pos1"]["ten_god"] == "Bi Jian"
    assert profile["pos2"]["ten_god"] == "Jie Cai"
    assert profile["pos3"]["ten_god"] == "Qi Sha"
    assert profile["pos4"]["ten_god"] == "Zheng Guan"

def test_calculate_ten_gods_xin():
    dm = "Xin"
    stems = {"pos1": "Xin", "pos2": "Geng", "pos3": "Bing", "pos4": "Ding"}
    res = calculate_ten_gods(dm, stems)
    profile = res["ten_gods_profile"]

    assert profile["pos1"]["ten_god"] == "Bi Jian"
    assert profile["pos2"]["ten_god"] == "Jie Cai"
    assert profile["pos3"]["ten_god"] == "Zheng Guan"
    assert profile["pos4"]["ten_god"] == "Qi Sha"

def test_calculate_ten_gods_all_dm_stems():
    # 10 Day Masters mapping test
    dms = ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]
    for dm in dms:
        res = calculate_ten_gods(dm, {"self": dm})
        assert res["ten_gods_profile"]["self"]["ten_god"] == "Bi Jian"
