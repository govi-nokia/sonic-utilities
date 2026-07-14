from show.lldp import (
    build_global_display_rows,
    build_port_display_rows,
    merge_global_defaults,
    tlv_display_value,
    config,
    interfaces,
    interface,
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
