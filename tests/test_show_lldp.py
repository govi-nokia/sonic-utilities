from show.lldp import (
    build_global_display_rows,
    build_port_display_rows,
    build_statistics_display_rows,
    collect_lldp_statistics,
    build_custom_tlv_display_rows,
    merge_global_defaults,
    tlv_display_value,
    config,
    interfaces,
    interface,
    statistics,
    custom_tlv,
)
from unittest.mock import patch
from click.testing import CliRunner
from utilities_common.db import Db
import pytest


@pytest.fixture
def db():
    return Db()


def test_merge_global_defaults_empty():
    merged = merge_global_defaults({})
    assert merged["enabled"] == "true"
    assert merged["hello_time"] == "30"
    assert merged["multiplier"] == "4"


def test_tlv_display_value():
    assert tlv_display_value("true") == "suppress"
    assert tlv_display_value("false") == "advertise"


def test_build_global_display_rows_with_config():
    entry = {
        "enabled": "false",
        "mode": "TRANSMIT",
        "hello_time": "45",
        "multiplier": "6",
        "system_name": "sw1",
        "system_description": "sonic",
        "supp_mgmt_address_tlv": "true",
        "supp_system_capabilities_tlv": "false",
    }
    rows = dict(build_global_display_rows(entry))
    assert rows["Enabled"] == "false"
    assert rows["Mode"] == "TRANSMIT"
    assert rows["Hello-time (sec)"] == "45"
    assert rows["Multiplier"] == "6"
    assert rows["System-name"] == "sw1"
    assert rows["System-description"] == "sonic"
    assert rows["Management-interface"] == "-"
    assert rows["Mgmt-address-TLV"] == "suppress"
    assert rows["System-capabilities-TLV"] == "advertise"


def test_build_global_display_rows_defaults_only():
    rows = dict(build_global_display_rows({}))
    assert rows["Enabled"] == "true"
    assert rows["Hello-time (sec)"] == "30"
    assert rows["Mode"] == "-"


def test_build_port_display_rows():
    port_table = {
        "Ethernet0": {"enabled": "true", "mode": "TRANSMIT"},
        "Ethernet4": {"enabled": "false"},
    }
    header, body = build_port_display_rows(port_table)
    assert header == ["Interface", "Enabled", "Mode"]
    assert ["Ethernet0", "true", "TRANSMIT"] in body
    assert ["Ethernet4", "false", "-"] in body


def test_show_lldp_config_command(db):
    db.cfgdb.set_entry("LLDP", "GLOBAL", {
        "enabled": "true",
        "hello_time": "45",
    })
    runner = CliRunner()
    result = runner.invoke(config, obj=db)
    assert result.exit_code == 0
    assert "Hello-time (sec)" in result.output
    assert "45" in result.output


def test_show_lldp_interfaces_empty(db):
    runner = CliRunner()
    result = runner.invoke(interfaces, obj=db)
    assert result.exit_code == 0
    assert "No per-interface LLDP configuration found" in result.output


def test_show_lldp_interfaces_with_data(db):
    db.cfgdb.set_entry("LLDP_PORT", "Ethernet0", {
        "enabled": "true",
        "mode": "RECEIVE",
    })
    runner = CliRunner()
    result = runner.invoke(interfaces, obj=db)
    assert result.exit_code == 0
    assert "Ethernet0" in result.output
    assert "RECEIVE" in result.output


@patch("config.main.interface_name_is_valid", return_value=True)
def test_show_lldp_interface_with_data(mock_valid, db):
    db.cfgdb.set_entry("LLDP_PORT", "Ethernet0", {
        "enabled": "false",
        "mode": "TRANSMIT",
    })
    runner = CliRunner()
    result = runner.invoke(interface, ["Ethernet0"], obj=db)
    assert result.exit_code == 0
    assert "Ethernet0" in result.output
    assert "false" in result.output


@patch("config.main.interface_name_is_valid", return_value=True)
def test_show_lldp_interface_missing(mock_valid, db):
    runner = CliRunner()
    result = runner.invoke(interface, ["Ethernet0"], obj=db)
    assert result.exit_code == 0
    assert "No LLDP configuration found" in result.output


SAMPLE_LLDP_STATS = {
    "Ethernet0": {
        "frame_in": "200",
        "frame_out": "100",
        "frame_discard": "6",
        "tlv_unknown": "7",
        "tlv_accepted": "9",
        "entries_aged_out": "8",
    },
    "eth0": {
        "frame_in": "20",
        "frame_out": "10",
        "frame_discard": "1",
        "tlv_unknown": "2",
        "tlv_accepted": "4",
        "entries_aged_out": "3",
    },
    "GLOBAL": {
        "frame_in": "220",
        "frame_out": "110",
        "frame_discard": "7",
        "tlv_unknown": "9",
        "tlv_accepted": "13",
        "entries_aged_out": "11",
    },
}


def _lldp_stat_keys(db):
    return db.db.keys(db.db.COUNTERS_DB, "LLDP_STATISTICS:*") or []


def _clear_lldp_stats(db):
    for key in _lldp_stat_keys(db):
        db.db.delete(db.db.COUNTERS_DB, key)


def _load_lldp_stats(db, samples=None):
    _clear_lldp_stats(db)
    for ifname, fields in (samples or SAMPLE_LLDP_STATS).items():
        key = "LLDP_STATISTICS:{}".format(ifname)
        for field, value in fields.items():
            db.db.set(db.db.COUNTERS_DB, key, field, value)


def test_build_statistics_display_rows_orders_global_last():
    header, body = build_statistics_display_rows([
        ("GLOBAL", SAMPLE_LLDP_STATS["GLOBAL"]),
        ("Ethernet4", {"frame_in": "1", "frame_out": "2"}),
        ("Ethernet0", SAMPLE_LLDP_STATS["Ethernet0"]),
    ])
    assert header == [
        "Interface", "Transmitted", "Received", "Discarded",
        "Unrecognized", "Ageout", "Inserted",
    ]
    assert body[0][0] == "Ethernet0"
    assert body[0][1] == "100"
    assert body[0][2] == "200"
    assert body[1][0] == "Ethernet4"
    assert body[1][1] == "2"
    assert body[1][2] == "1"
    assert body[1][3] == "0"
    assert body[-1][0] == "GLOBAL"
    assert body[-1][1] == "110"
    assert body[-1][2] == "220"


def test_collect_and_show_lldp_statistics(db):
    _load_lldp_stats(db)
    try:
        parsed = dict(collect_lldp_statistics(db.db))
        assert parsed["Ethernet0"]["frame_in"] == "200"
        assert parsed["eth0"]["frame_out"] == "10"
        assert parsed["GLOBAL"]["tlv_accepted"] == "13"

        runner = CliRunner()
        result = runner.invoke(statistics, obj=db)
        assert result.exit_code == 0
        assert "Ethernet0" in result.output
        assert "eth0" in result.output
        assert "GLOBAL" in result.output
        assert "200" in result.output
        assert "220" in result.output
        # GLOBAL is the last data row
        data_rows = [ln for ln in result.output.splitlines() if ln.strip()]
        assert "GLOBAL" in data_rows[-1]
    finally:
        _clear_lldp_stats(db)


def test_show_lldp_statistics_one_interface(db):
    _load_lldp_stats(db)
    try:
        runner = CliRunner()
        result = runner.invoke(statistics, ["Ethernet0"], obj=db)
        assert result.exit_code == 0
        assert "Ethernet0" in result.output
        assert "200" in result.output
        assert "eth0" not in result.output
        assert "GLOBAL" not in result.output
    finally:
        _clear_lldp_stats(db)


def test_show_lldp_statistics_missing(db):
    _clear_lldp_stats(db)
    runner = CliRunner()
    result = runner.invoke(statistics, obj=db)
    assert result.exit_code == 0
    assert "No LLDP statistics found" in result.output

    result = runner.invoke(statistics, ["Ethernet0"], obj=db)
    assert result.exit_code == 0
    assert "No LLDP statistics found for Ethernet0" in result.output


def test_build_custom_tlv_display_rows():
    header, body = build_custom_tlv_display_rows({
        "vendor-serial": {
            "type": "127",
            "oui": "00:90:69",
            "oui_subtype": "1",
            "value": "aabb",
        },
    })
    assert header[0] == "Name"
    assert body[0][0] == "vendor-serial"
    assert body[0][2] == "00:90:69"


def test_show_lldp_custom_tlv(db):
    db.cfgdb.set_entry("LLDP_CUSTOM_TLV", "vendor-serial", {
        "type": "127",
        "oui": "00:90:69",
        "oui_subtype": "1",
        "value": "aabb",
    })
    runner = CliRunner()
    result = runner.invoke(custom_tlv, obj=db)
    assert result.exit_code == 0
    assert "vendor-serial" in result.output
    assert "00:90:69" in result.output


def test_show_lldp_custom_tlv_empty(db):
    runner = CliRunner()
    result = runner.invoke(custom_tlv, obj=db)
    assert result.exit_code == 0
    assert "No LLDP custom TLVs configured" in result.output
