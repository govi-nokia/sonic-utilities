#
# 'lldp' group ('config lldp ...')
#

import re

import click
import utilities_common.cli as clicommon
from jsonpatch import JsonPatchConflict

from .validated_config_db_connector import ValidatedConfigDBConnector

LLDP_GLOBAL_TABLE = "LLDP"
LLDP_GLOBAL_KEY = "GLOBAL"
LLDP_PORT_TABLE = "LLDP_PORT"

HELLO_TIME_MIN = 5
HELLO_TIME_MAX = 254
MULTIPLIER_MIN = 1
MULTIPLIER_MAX = 10

MODE_CHOICES = ["receive", "transmit"]
MODE_DB_MAP = {
    "receive": "RECEIVE",
    "transmit": "TRANSMIT",
}

# OpenConfig management-interface is a single ifname, not an lldpd glob.
_MGMT_IFNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._/-]{0,31}$")


def _config_db(db):
    return ValidatedConfigDBConnector(db.cfgdb)


def _mod_global(ctx, db, fields):
    """Merge fields into LLDP|GLOBAL, preserving other configured values."""
    config_db = _config_db(db)
    try:
        entry = config_db.get_entry(LLDP_GLOBAL_TABLE, LLDP_GLOBAL_KEY) or {}
        entry.update(fields)
        config_db.set_entry(LLDP_GLOBAL_TABLE, LLDP_GLOBAL_KEY, entry)
    except (ValueError, JsonPatchConflict) as exc:
        ctx.fail("Failed to save to ConfigDB. Error: {}".format(exc))


def _mod_port(ctx, db, ifname, fields):
    """Merge fields into LLDP_PORT|<ifname>."""
    config_db = _config_db(db)
    try:
        entry = config_db.get_entry(LLDP_PORT_TABLE, ifname) or {}
        entry.update(fields)
        config_db.set_entry(LLDP_PORT_TABLE, ifname, entry)
    except (ValueError, JsonPatchConflict) as exc:
        ctx.fail("Failed to save to ConfigDB. Error: {}".format(exc))


def _validate_hello_time(ctx, hello_time):
    if hello_time not in range(HELLO_TIME_MIN, HELLO_TIME_MAX + 1):
        ctx.fail("LLDP hello-time must be in range {}-{}".format(
            HELLO_TIME_MIN, HELLO_TIME_MAX))


def _validate_multiplier(ctx, multiplier):
    if multiplier not in range(MULTIPLIER_MIN, MULTIPLIER_MAX + 1):
        ctx.fail("LLDP multiplier must be in range {}-{}".format(
            MULTIPLIER_MIN, MULTIPLIER_MAX))


def _del_global_field(ctx, db, field):
    config_db = _config_db(db)
    try:
        entry = config_db.get_entry(LLDP_GLOBAL_TABLE, LLDP_GLOBAL_KEY) or {}
        if field in entry:
            del entry[field]
        if entry:
            config_db.set_entry(LLDP_GLOBAL_TABLE, LLDP_GLOBAL_KEY, entry)
        else:
            config_db.set_entry(LLDP_GLOBAL_TABLE, LLDP_GLOBAL_KEY, None)
    except (ValueError, JsonPatchConflict) as exc:
        ctx.fail("Failed to save to ConfigDB. Error: {}".format(exc))


def _validate_interface(ctx, db, ifname):
    from config.main import interface_name_is_valid
    if interface_name_is_valid(db.cfgdb, ifname) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")


def _management_interface_exists(config_db, ifname):
    """True if ifname is a configured PORT, LAG, VLAN, loopback, or mgmt port."""
    try:
        from config.main import interface_name_is_valid
        if interface_name_is_valid(config_db, ifname):
            return True
    except Exception:
        pass
    for table in ("MGMT_PORT", "VLAN"):
        if ifname in (config_db.get_table(table) or {}):
            return True
    for table in ("MGMT_INTERFACE", "VLAN_INTERFACE"):
        for key in (config_db.get_table(table) or {}):
            name = key[0] if isinstance(key, (tuple, list)) else str(key).split("|", 1)[0]
            if name == ifname:
                return True
    return False


def _validate_management_interface(ctx, db, ifname):
    if not _MGMT_IFNAME_RE.match(ifname or ""):
        ctx.fail("Invalid management interface name")
        return
    if not _management_interface_exists(db.cfgdb, ifname):
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")


def _db_mode(mode):
    return MODE_DB_MAP[mode.lower()]


@click.group(cls=clicommon.AbbreviationGroup, name="lldp")
def lldp():
    """LLDP configuration"""
    pass


@lldp.command("enable")
@clicommon.pass_db
def lldp_enable(db):
    """Enable LLDP globally"""
    ctx = click.get_current_context()
    _mod_global(ctx, db, {"enabled": "true"})


@lldp.command("disable")
@clicommon.pass_db
def lldp_disable(db):
    """Disable LLDP globally"""
    ctx = click.get_current_context()
    _mod_global(ctx, db, {"enabled": "false"})


@lldp.command("hello-time")
@click.argument("hello_time", metavar="<5-254>", required=True, type=int)
@clicommon.pass_db
def lldp_hello_time(db, hello_time):
    """Configure LLDP hello interval in seconds"""
    ctx = click.get_current_context()
    _validate_hello_time(ctx, hello_time)
    _mod_global(ctx, db, {"hello_time": str(hello_time)})


@lldp.command("multiplier")
@click.argument("multiplier", metavar="<1-10>", required=True, type=int)
@clicommon.pass_db
def lldp_multiplier(db, multiplier):
    """Configure LLDP hold multiplier"""
    ctx = click.get_current_context()
    _validate_multiplier(ctx, multiplier)
    _mod_global(ctx, db, {"multiplier": str(multiplier)})


@lldp.command("system-name")
@click.argument("name", metavar="<name>", required=True)
@clicommon.pass_db
def lldp_system_name(db, name):
    """Configure LLDP system name"""
    ctx = click.get_current_context()
    _mod_global(ctx, db, {"system_name": name})


@lldp.command("system-description")
@click.argument("description", metavar="<description>", required=True)
@clicommon.pass_db
def lldp_system_description(db, description):
    """Configure LLDP system description"""
    ctx = click.get_current_context()
    _mod_global(ctx, db, {"system_description": description})


@lldp.command("management-interface")
@click.argument("ifname", metavar="<interface_name>", required=True)
@clicommon.pass_db
def lldp_management_interface(db, ifname):
    """Set the interface used for the Management Address TLV"""
    ctx = click.get_current_context()
    _validate_management_interface(ctx, db, ifname)
    _mod_global(ctx, db, {"management_interface": ifname})


@lldp.command("mode")
@click.argument("mode", metavar="<receive|transmit>", required=True,
                type=click.Choice(MODE_CHOICES, case_sensitive=False))
@clicommon.pass_db
def lldp_mode(db, mode):
    """Configure global LLDP mode"""
    ctx = click.get_current_context()
    _mod_global(ctx, db, {"mode": _db_mode(mode)})


@lldp.command("management-addresses-advertisements")
@clicommon.pass_db
def lldp_mgmt_addr_advertise(db):
    """Advertise management address TLV in LLDP frames"""
    ctx = click.get_current_context()
    _mod_global(ctx, db, {"supp_mgmt_address_tlv": "false"})


@lldp.command("capabilities-advertisements")
@clicommon.pass_db
def lldp_capabilities_advertise(db):
    """Advertise system capabilities TLV in LLDP frames"""
    ctx = click.get_current_context()
    _mod_global(ctx, db, {"supp_system_capabilities_tlv": "false"})


@lldp.group("unconfigure")
def lldp_unconfigure():
    """Suppress LLDP TLV advertisements"""
    pass


@lldp_unconfigure.command("management-addresses-advertisements")
@clicommon.pass_db
def lldp_unconfigure_mgmt_addr(db):
    """Suppress management address TLV in LLDP frames"""
    ctx = click.get_current_context()
    _mod_global(ctx, db, {"supp_mgmt_address_tlv": "true"})


@lldp_unconfigure.command("capabilities-advertisements")
@clicommon.pass_db
def lldp_unconfigure_capabilities(db):
    """Suppress system capabilities TLV in LLDP frames"""
    ctx = click.get_current_context()
    _mod_global(ctx, db, {"supp_system_capabilities_tlv": "true"})


@lldp_unconfigure.command("management-interface")
@clicommon.pass_db
def lldp_unconfigure_management_interface(db):
    """Clear the Management Address TLV interface (use first MGMT_INTERFACE IP)"""
    ctx = click.get_current_context()
    _del_global_field(ctx, db, "management_interface")


@lldp.group("custom-tlv")
def lldp_custom_tlv():
    """Advertise organizationally specific LLDP TLVs"""
    pass


def _normalize_oui(ctx, oui):
    cleaned = "".join(ch for ch in oui if ch not in ":,- \t")
    if len(cleaned) != 6:
        ctx.fail("OUI must be 3 bytes (for example 00:90:69)")
    try:
        bytes.fromhex(cleaned)
    except ValueError:
        ctx.fail("OUI must be hexadecimal")
    return "{}:{}:{}".format(cleaned[0:2], cleaned[2:4], cleaned[4:6]).lower()


def _normalize_hex_value(ctx, value):
    if value is None:
        return ""
    cleaned = "".join(ch for ch in value if ch not in ":,- \t")
    if cleaned == "":
        return ""
    if len(cleaned) % 2:
        ctx.fail("TLV value must be an even number of hex digits")
    try:
        bytes.fromhex(cleaned)
    except ValueError:
        ctx.fail("TLV value must be hexadecimal")
    return cleaned.lower()


@lldp_custom_tlv.command("add")
@click.argument("name", metavar="<name>", required=True)
@click.argument("oui", metavar="<oui>", required=True)
@click.argument("subtype", metavar="<subtype>", required=True, type=int)
@click.argument("value", metavar="<hex-value>", required=False)
@clicommon.pass_db
def lldp_custom_tlv_add(db, name, oui, subtype, value):
    """Add or replace a globally advertised custom TLV"""
    ctx = click.get_current_context()
    if subtype not in range(0, 256):
        ctx.fail("Subtype must be in range 0-255")
    fields = {
        "type": "127",
        "oui": _normalize_oui(ctx, oui),
        "oui_subtype": str(subtype),
    }
    hex_value = _normalize_hex_value(ctx, value)
    if hex_value:
        fields["value"] = hex_value
    config_db = _config_db(db)
    try:
        config_db.set_entry("LLDP_CUSTOM_TLV", name, fields)
    except (ValueError, JsonPatchConflict) as exc:
        ctx.fail("Failed to save to ConfigDB. Error: {}".format(exc))


@lldp_custom_tlv.command("delete")
@click.argument("name", metavar="<name>", required=True)
@clicommon.pass_db
def lldp_custom_tlv_delete(db, name):
    """Remove a globally advertised custom TLV"""
    ctx = click.get_current_context()
    config_db = _config_db(db)
    try:
        config_db.set_entry("LLDP_CUSTOM_TLV", name, None)
    except (ValueError, JsonPatchConflict) as exc:
        ctx.fail("Failed to save to ConfigDB. Error: {}".format(exc))


@lldp.group("interface")
@clicommon.pass_db
def lldp_interface(_db):
    """Per-interface LLDP configuration"""
    pass


@lldp_interface.command("enable")
@click.argument("ifname", metavar="<interface_name>", required=True)
@clicommon.pass_db
def lldp_interface_enable(db, ifname):
    """Enable LLDP on an interface"""
    ctx = click.get_current_context()
    _validate_interface(ctx, db, ifname)
    _mod_port(ctx, db, ifname, {"enabled": "true"})


@lldp_interface.command("disable")
@click.argument("ifname", metavar="<interface_name>", required=True)
@clicommon.pass_db
def lldp_interface_disable(db, ifname):
    """Disable LLDP on an interface"""
    ctx = click.get_current_context()
    _validate_interface(ctx, db, ifname)
    _mod_port(ctx, db, ifname, {"enabled": "false"})


@lldp_interface.command("mode")
@click.argument("ifname", metavar="<interface_name>", required=True)
@click.argument("mode", metavar="<receive|transmit>", required=True,
                type=click.Choice(MODE_CHOICES, case_sensitive=False))
@clicommon.pass_db
def lldp_interface_mode(db, ifname, mode):
    """Configure per-interface LLDP mode"""
    ctx = click.get_current_context()
    _validate_interface(ctx, db, ifname)
    _mod_port(ctx, db, ifname, {"mode": _db_mode(mode)})


@lldp_interface.command("default")
@click.argument("ifname", metavar="<interface_name>", required=True)
@clicommon.pass_db
def lldp_interface_default(db, ifname):
    """Remove per-interface LLDP override (revert to global settings)"""
    ctx = click.get_current_context()
    _validate_interface(ctx, db, ifname)
    config_db = _config_db(db)
    try:
        config_db.set_entry(LLDP_PORT_TABLE, ifname, None)
    except (ValueError, JsonPatchConflict) as exc:
        ctx.fail("Failed to save to ConfigDB. Error: {}".format(exc))
