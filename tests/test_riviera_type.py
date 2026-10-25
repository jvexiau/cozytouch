"""A recognised Riviera uses the existing towel-rack mapping, not a new driver.

The owner identifies a towel dryer; the same linked THZONE reports device
type 7 in the vendor's enum. Only the two known commercial labels are typed.
Room slots, unrelated heaters and their existing mappings are not overridden.
"""

import copy
from types import SimpleNamespace

import pytest
from test_riviera_discovery import account, devices

from custom_components.cozytouch.capability import get_capability_infos
from custom_components.cozytouch.hub import Hub
from custom_components.cozytouch.model import (
    CozytouchDeviceType,
    get_device_model_infos,
    get_model_infos,
)


@pytest.mark.parametrize("product", ["RIVIERA 2 1750W", "RIVIERA 2 1750W BLC SAT"])
def test_only_the_recognised_riviera_room_becomes_a_towel_rack(product):
    reported = devices(product)
    original = copy.deepcopy(reported)
    infos = get_device_model_infos(reported, reported[1])
    assert infos.type is CozytouchDeviceType.TOWEL_RACK
    assert infos.modelId == 557
    assert infos.name == product
    assert infos.HVACModes == {0: "off", 4: "heat"}
    assert not ({"fanModes", "swingModes", "quietModeAvailable"} & infos.keys())
    assert infos.awayModeTemperatureAvailable is False
    assert infos.ecoModeAvailable is False
    zone = get_device_model_infos(reported, reported[2])
    assert zone.type is CozytouchDeviceType.ZONE
    assert reported == original


@pytest.mark.parametrize("modelId", [804, 3424])
def test_the_commercial_model_uses_the_normal_override_layer(modelId):
    infos = get_model_infos(modelId)
    assert infos.type is CozytouchDeviceType.TOWEL_RACK
    assert infos.HVACModes == {0: "off", 4: "heat"}


@pytest.mark.parametrize("modelId", [557, 558, 559, 560, 561, 1736])
def test_no_global_room_model_override_is_added(modelId):
    assert get_model_infos(modelId).type is CozytouchDeviceType.ROOM


@pytest.mark.parametrize("change", ["unlinked", "other_product", "other_gateway"])
def test_unrecognised_rooms_stay_rooms(change):
    reported = devices()
    if change == "unlinked":
        reported[1]["tags"] = []
    elif change == "other_product":
        reported[2]["longName"] = "OTHER HEATER"
    else:
        reported[2]["masterDeviceId"] = 999
    infos = get_device_model_infos(reported, reported[1])
    assert infos.type is CozytouchDeviceType.ROOM


def test_a_second_room_on_the_same_gateway_is_not_retyped():
    reported = devices()
    other = copy.deepcopy(reported[1])
    other.update(deviceId=4, name="ROOM_1", productId=27, modelId=558, tags=[])
    reported.append(other)
    recognised = get_device_model_infos(reported, reported[1])
    assert recognised.type is CozytouchDeviceType.TOWEL_RACK
    assert get_device_model_infos(reported, other).type is CozytouchDeviceType.ROOM


def test_the_hub_builds_capabilities_with_the_towel_rack_type():
    reported = devices()
    reported[1]["capabilities"] = [
        {"capabilityId": i, "value": value} for i, value in {
            7: "4", 40: "19", 117: "20", 153: "0", 157: "0", 158: "120",
            159: "60", 172: "7", 181: "4", 184: "0", 100022: "415",
            100506: "0", 100507: "0", 100801: "1", 100802: "0", 100803: "1",
            100804: "0", 104044: "0",
        }.items()
    ]
    hub = SimpleNamespace(_account=account(reported), _deviceId=2, _create_unknown=True)
    built = {c.capabilityId: c for c in Hub.get_capabilities_for_device(hub)}
    infos = get_device_model_infos(reported, reported[1])
    available = {c["capabilityId"] for c in reported[1]["capabilities"]}
    assert built[7].name == "heat"
    assert built[7].modelId == 557
    assert built[7].deviceId == 2
    assert built[7].progCapabilityId == 184
    assert not ({"fanModeCapabilityId", "quietModeCapabilityId",
                 "swingModeCapabilityId", "targetCoolCapabilityId"} & built[7].keys())
    assert built[158].name == "override_total_time"
    assert built[159].name == "override_remain_time"
    assert 100506 not in built
    assert 100507 not in built
    assert 172 not in built
    assert built[104044].type == "switch"
    assert built[104044] == (
        get_capability_infos(infos, 104044, "0", available) | {"deviceId": 2}
    )
