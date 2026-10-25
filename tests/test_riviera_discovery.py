"""Riviera discovery names the product without changing any control mapping.

Only the reported ROOM -> THZONE link on one CozyBox supplies the name.
Fixtures are synthetic; no account, API call or running HA is involved.
"""

import copy
from types import SimpleNamespace

import pytest

from custom_components.cozytouch.account import CozytouchAccount, room_product_name
from custom_components.cozytouch.capability import get_capability_infos
from custom_components.cozytouch.config_flow import _device_options, _subentry_for
from custom_components.cozytouch.hub import Hub, device_info_for
from custom_components.cozytouch.model import get_device_model_infos


def devices(product="RIVIERA 2 1750W", room="ROOM_0", zone="THZONE_0"):
    return [
        {"deviceId": 1, "modelId": 2447, "productId": 63,
         "name": "CozyBox", "modelFamily": "Connectivity_Box"},
        {"deviceId": 2, "modelId": 557, "productId": 26,
         "name": room, "customName": room, "masterDeviceId": 1, "zoneId": 10,
         "tags": [{"label": "iothubChildrenIds", "value": zone}],
         "capabilities": [{"capabilityId": 7, "value": "4"},
                          {"capabilityId": 40, "value": "19"}]},
        {"deviceId": 3, "modelId": 1505, "productId": 65,
         "name": zone, "longName": product, "masterDeviceId": 1},
    ]


def account(reported):
    stub = object.__new__(CozytouchAccount)
    stub.devices = reported
    stub.zones = [{"id": 10, "name": "Salle de bain"}]
    return stub


@pytest.mark.parametrize(("reported_name", "expected"), [
    ("RIVIERA 2 1750W", "RIVIERA 2 1750W"),
    ("  riviera  2 1750w  ", "RIVIERA 2 1750W"),
    ("RIVIERA 2 1750W BLC SAT", "RIVIERA 2 1750W BLC SAT"),
])
def test_the_name_is_the_catalogue_match_without_guessing_a_finish(
    reported_name, expected,
):
    reported = devices(reported_name)
    assert room_product_name(reported, reported[1]) == expected


def test_the_picker_and_subentry_use_the_product_and_keep_the_room_id():
    reported = devices()
    summaries = account(reported).device_summaries()
    assert len(summaries) == 2
    assert summaries[1]["name"] == "RIVIERA 2 1750W (Salle de bain)"
    option = _device_options(summaries, taken={1})[0]
    assert option == {"label": "RIVIERA 2 1750W (Salle de bain)", "value": "2"}
    subentry = _subentry_for(summaries[1])
    assert subentry["title"] == option["label"]
    assert subentry["data"]["deviceId"] == 2
    assert subentry["unique_id"] == "cozytouch_2"
    assert reported[1]["name"] == "ROOM_0"


def test_an_app_custom_name_is_preserved_with_the_model_beside_it():
    reported = devices()
    reported[1]["customName"] = "Radiateur douche"
    summaries = account(reported).device_summaries()
    assert _device_options(summaries, taken={1})[0]["label"] == (
        "Radiateur douche (RIVIERA 2 1750W)"
    )


def test_a_product_without_a_named_zone_has_no_duplicate_label():
    stub = account(devices())
    stub.zones = []
    assert _device_options(stub.device_summaries(), taken={1})[0]["label"] == (
        "RIVIERA 2 1750W"
    )


@pytest.mark.parametrize("broken", [
    "missing_tag", "wrong_child", "other_gateway", "missing_gateway",
    "duplicate_child", "non_zone", "unknown_product", "other_wattage",
    "missing_product_name", "malformed_tag", "not_a_cozybox",
])
def test_incomplete_or_ambiguous_links_do_not_change_existing_names(broken):
    reported = devices()
    room, zone = reported[1:]
    if broken == "missing_tag":
        room["tags"] = []
    elif broken == "wrong_child":
        room["tags"][0]["value"] = "THZONE_9"
    elif broken == "other_gateway":
        zone["masterDeviceId"] = 999
    elif broken == "missing_gateway":
        reported.pop(0)
    elif broken == "duplicate_child":
        reported.append(zone.copy() | {"deviceId": 4})
    elif broken == "non_zone":
        zone["name"] = "ROOM_1"
        room["tags"][0]["value"] = "ROOM_1"
    elif broken == "unknown_product":
        zone["longName"] = "OTHER HEATER"
    elif broken == "other_wattage":
        zone["longName"] = "RIVIERA 2 1500W"
    elif broken == "missing_product_name":
        zone.pop("longName")
    elif broken == "malformed_tag":
        room["tags"] = [None, {"label": "iothubChildrenIds", "value": ["THZONE_0"]}]
    elif broken == "not_a_cozybox":
        reported[0]["modelFamily"] = "Air_Conditioning"
    assert room_product_name(reported, room) is None


def test_room_and_zone_indices_are_not_product_identifiers():
    reported = devices(room="ROOM_7", zone="THZONE_12")
    reported[1].update(modelId=1736, productId=99)
    assert room_product_name(reported, reported[1]) == "RIVIERA 2 1750W"


def test_another_room_in_the_same_zone_is_not_misidentified():
    reported = devices()
    other_room = copy.deepcopy(reported[1])
    other_room.update(deviceId=4, name="ROOM_1", customName="ROOM_1")
    other_room["tags"] = []
    reported.append(other_room)
    assert room_product_name(reported, other_room) is None


def test_unrecognised_devices_keep_their_existing_picker_format():
    other = {"deviceId": 9, "name": "Existing name", "model": "Existing name"}
    assert _device_options([other], set())[0]["label"] == (
        "Existing name (Existing name)"
    )
    reported = devices("OTHER HEATER")
    summaries = account(reported).device_summaries()
    assert summaries[1]["name"] == "ROOM_0"
    assert summaries[1]["model"] == "Room (#1)"
    assert "product_name" not in summaries[1]


def test_the_device_registry_uses_the_product_without_changing_its_identity():
    reported = devices()
    hub = SimpleNamespace(_account=account(reported), _deviceId=2)
    hub.get_zone_name = lambda zoneId: hub._account.get_zone_name(zoneId)
    hub.get_model_infos = lambda: Hub.get_model_infos(hub)
    hub.get_serial_number = lambda: "fixture"
    hub.get_software_version = lambda: None
    hub.get_via_device = lambda: None
    info = device_info_for(hub, "existing-subentry")
    assert info["name"] == "RIVIERA 2 1750W"
    assert info["model"] == "RIVIERA 2 1750W"
    assert info["identifiers"] == {("cozytouch", "existing-subentry")}
    mapped = get_device_model_infos(reported, reported[1], "Salle de bain")
    displayed = hub.get_model_infos()
    assert {k: v for k, v in displayed.items() if k != "name"} == {
        k: v for k, v in mapped.items() if k != "name"
    }


def test_detection_leaves_all_model_and_capability_answers_unchanged():
    reported = devices()
    original = copy.deepcopy(reported)
    model = get_device_model_infos(reported, reported[1])
    before = {
        i: get_capability_infos(model, i, "0", {7, 40, 104044})
        for i in (7, 40, 360, 100505, 104044)
    }
    assert room_product_name(reported, reported[1]) == "RIVIERA 2 1750W"
    after_model = get_device_model_infos(reported, reported[1])
    assert after_model == model
    assert {
        i: get_capability_infos(after_model, i, "0", {7, 40, 104044})
        for i in before
    } == before
    assert reported == original
