import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from utilities_common.db import Db

from config.lldp import (
    lldp_enable,
    lldp_disable,
    lldp_hello_time,
    lldp_multiplier,
    lldp_system_name,
    lldp_mode,
    lldp_mgmt_addr_advertise,
    lldp_unconfigure_mgmt_addr,
    lldp_interface_enable,
    lldp_interface_mode,
    lldp_interface_default,
    _validate_hello_time,
    _validate_multiplier,
    _db_mode,
)


@pytest.fixture
def db():
    return Db()


def test_db_mode_mapping():
    assert _db_mode("receive") == "RECEIVE"
    assert _db_mode("transmit") == "TRANSMIT"


def test_validate_hello_time_invalid():
    ctx = MagicMock()
    _validate_hello_time(ctx, 4)
    ctx.fail.assert_called_once_with(
        "LLDP hello-time must be in range 5-254")


def test_validate_multiplier_invalid():
    ctx = MagicMock()
    _validate_multiplier(ctx, 11)
    ctx.fail.assert_called_once_with(
        "LLDP multiplier must be in range 1-10")


def test_lldp_enable_merges_global_entry(db):
    db.cfgdb.set_entry("LLDP", "GLOBAL", {"hello_time": "30"})
    runner = CliRunner()
    result = runner.invoke(lldp_enable, obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP", "GLOBAL") == {
        "hello_time": "30", "enabled": "true"
    }


def test_lldp_disable(db):
    runner = CliRunner()
    result = runner.invoke(lldp_disable, obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP", "GLOBAL") == {"enabled": "false"}


def test_lldp_hello_time_valid(db):
    runner = CliRunner()
    result = runner.invoke(lldp_hello_time, ["45"], obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP", "GLOBAL") == {"hello_time": "45"}


def test_lldp_hello_time_invalid(db):
    runner = CliRunner()
    result = runner.invoke(lldp_hello_time, ["4"], obj=db)
    assert result.exit_code != 0
    assert "hello-time must be in range" in result.output


def test_lldp_multiplier_valid(db):
    runner = CliRunner()
    result = runner.invoke(lldp_multiplier, ["6"], obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP", "GLOBAL") == {"multiplier": "6"}


def test_lldp_system_name(db):
    runner = CliRunner()
    result = runner.invoke(lldp_system_name, ["my-switch"], obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP", "GLOBAL") == {"system_name": "my-switch"}


def test_lldp_mode(db):
    runner = CliRunner()
    result = runner.invoke(lldp_mode, ["transmit"], obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP", "GLOBAL") == {"mode": "TRANSMIT"}


def test_lldp_mgmt_addr_advertise(db):
    runner = CliRunner()
    result = runner.invoke(lldp_mgmt_addr_advertise, obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP", "GLOBAL") == {
        "supp_mgmt_address_tlv": "false"
    }


def test_lldp_unconfigure_mgmt_addr(db):
    runner = CliRunner()
    result = runner.invoke(lldp_unconfigure_mgmt_addr, obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP", "GLOBAL") == {
        "supp_mgmt_address_tlv": "true"
    }


@patch("config.main.interface_name_is_valid", return_value=True)
def test_lldp_interface_enable(mock_valid, db):
    runner = CliRunner()
    result = runner.invoke(lldp_interface_enable, ["Ethernet0"], obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP_PORT", "Ethernet0") == {"enabled": "true"}


@patch("config.main.interface_name_is_valid", return_value=True)
def test_lldp_interface_mode(mock_valid, db):
    runner = CliRunner()
    result = runner.invoke(lldp_interface_mode, ["Ethernet0", "receive"], obj=db)
    assert result.exit_code == 0
    assert db.cfgdb.get_entry("LLDP_PORT", "Ethernet0") == {"mode": "RECEIVE"}


@patch("config.main.interface_name_is_valid", return_value=True)
def test_lldp_interface_default(mock_valid, db):
    db.cfgdb.set_entry("LLDP_PORT", "Ethernet0", {"enabled": "false"})
    runner = CliRunner()
    result = runner.invoke(lldp_interface_default, ["Ethernet0"], obj=db)
    assert result.exit_code == 0
    assert not db.cfgdb.get_entry("LLDP_PORT", "Ethernet0")
