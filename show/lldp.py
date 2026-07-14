#
# 'lldp' group ("show lldp ...")
#
# Augments the existing sonic-utilities LLDP show CLI:
#   neighbors / table  - runtime neighbor data via lldpshow (unchanged behavior)
#   config / interfaces / interface - CONFIG_DB settings written by 'config lldp'
#   statistics - COUNTERS_DB LLDP_STATISTICS written by lldp_syncd
#

import click
import utilities_common.cli as clicommon
from natsort import natsorted
from tabulate import tabulate

LLDP_GLOBAL_TABLE = "LLDP"
LLDP_GLOBAL_KEY = "GLOBAL"
LLDP_PORT_TABLE = "LLDP_PORT"
LLDP_CUSTOM_TLV_TABLE = "LLDP_CUSTOM_TLV"
LLDP_STATISTICS_TABLE = "LLDP_STATISTICS"
LLDP_STATISTICS_GLOBAL_KEY = "GLOBAL"

# COUNTERS_DB field -> CLI column. Labels and order match
# `lldpcli show statistics` (Transmitted/Received/Discarded/Unrecognized/
# Ageout/Inserted). `Deleted` is not stored in COUNTERS_DB.
LLDP_STAT_FIELDS = (
    ("frame_out", "Transmitted"),
    ("frame_in", "Received"),
    ("frame_discard", "Discarded"),
    ("tlv_unknown", "Unrecognized"),
    ("entries_aged_out", "Ageout"),
    ("tlv_accepted", "Inserted"),
)

LLDP_GLOBAL_DEFAULTS = {
    "enabled": "true",
    "hello_time": "30",
    "multiplier": "4",
    "supp_mgmt_address_tlv": "false",
    "supp_system_capabilities_tlv": "false",
}

GLOBAL_DISPLAY_FIELDS = [
    ("enabled", "Enabled"),
    ("mode", "Mode"),
    ("hello_time", "Hello-time (sec)"),
    ("multiplier", "Multiplier"),
    ("system_name", "System-name"),
    ("system_description", "System-description"),
    ("management_interface", "Management-interface"),
    ("mgmt_address_tlv", "Mgmt-address-TLV"),
    ("system_capabilities_tlv", "System-capabilities-TLV"),
]


def merge_global_defaults(entry):
    return {**LLDP_GLOBAL_DEFAULTS, **(entry or {})}


def tlv_display_value(suppress):
    return "suppress" if suppress == "true" else "advertise"


def build_global_display_rows(entry):
    """Return key/value rows for global LLDP configuration display."""
    merged = merge_global_defaults(entry)
    rows = []
    for field, label in GLOBAL_DISPLAY_FIELDS:
        if field == "mgmt_address_tlv":
            value = tlv_display_value(merged["supp_mgmt_address_tlv"])
        elif field == "system_capabilities_tlv":
            value = tlv_display_value(merged["supp_system_capabilities_tlv"])
        else:
            value = merged.get(field, "")
        rows.append([label, value if value != "" else "-"])
    return rows


def build_port_display_rows(port_table, ifname=None):
    """Return tabular rows for per-interface LLDP configuration."""
    header = ["Interface", "Enabled", "Mode"]
    body = []
    keys = [ifname] if ifname else natsorted(port_table.keys())
    for name in keys:
        entry = port_table.get(name, {})
        body.append([
            name,
            entry.get("enabled", "-"),
            entry.get("mode", "-"),
        ])
    return header, body


def build_custom_tlv_display_rows(table):
    """Return tabular rows for advertised custom TLVs."""
    header = ["Name", "Type", "OUI", "Subtype", "Value"]
    body = []
    for name in natsorted(table.keys()):
        entry = table.get(name) or {}
        body.append([
            name,
            entry.get("type", "127"),
            entry.get("oui", "-"),
            entry.get("oui_subtype", "-"),
            entry.get("value", "-") or "-",
        ])
    return header, body


def collect_lldp_statistics(counters_db, ifname=None):
    """Read LLDP_STATISTICS hashes from COUNTERS_DB.

    Returns a list of (interface_or_GLOBAL, field_dict) tuples. Missing
    hashes are omitted (a single-interface lookup that does not exist
    yields an empty list).
    """
    if counters_db is None:
        return []

    separator = counters_db.get_db_separator(counters_db.COUNTERS_DB)
    prefix = LLDP_STATISTICS_TABLE + separator
    if ifname:
        key_list = [prefix + ifname]
    else:
        key_list = counters_db.keys(counters_db.COUNTERS_DB, prefix + "*") or []

    entries = []
    for key in key_list:
        if isinstance(key, bytes):
            key = key.decode()
        fields = counters_db.get_all(counters_db.COUNTERS_DB, key)
        if not fields:
            continue
        name = key.split(separator, 1)[1] if separator in key else key
        decoded = {}
        for field, value in fields.items():
            if isinstance(field, bytes):
                field = field.decode()
            if isinstance(value, bytes):
                value = value.decode()
            decoded[field] = value
        entries.append((name, decoded))
    return entries


def build_statistics_display_rows(entries):
    """Return header and tabular rows for LLDP statistics.

    Per-interface rows are natsorted; GLOBAL is always last when present.
    Missing counter fields display as 0.
    """
    header = ["Interface"] + [label for _, label in LLDP_STAT_FIELDS]
    by_name = {name: fields for name, fields in entries}
    iface_names = [name for name in by_name if name != LLDP_STATISTICS_GLOBAL_KEY]
    ordered = natsorted(iface_names)
    if LLDP_STATISTICS_GLOBAL_KEY in by_name:
        ordered.append(LLDP_STATISTICS_GLOBAL_KEY)

    body = []
    for name in ordered:
        fields = by_name[name]
        body.append([name] + [fields.get(src, "0") for src, _ in LLDP_STAT_FIELDS])
    return header, body


@click.group(cls=clicommon.AliasedGroup)
def lldp():
    """Show LLDP information"""
    pass


# Default 'lldp' command (called if no subcommands or their aliases were passed)
@lldp.command()
@click.argument('interfacename', required=False)
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def neighbors(interfacename, verbose):
    """Show LLDP neighbors"""
    from show.main import run_command, iface_alias_converter

    cmd = ['sudo', 'lldpshow', '-d']

    if interfacename is not None:
        if clicommon.get_interface_naming_mode() == "alias":
            interfacename = iface_alias_converter.alias_to_name(interfacename)

        cmd += ['-p', str(interfacename)]

    run_command(cmd, display_cmd=verbose)


@lldp.command()
@click.option('--verbose', is_flag=True, help="Enable verbose output")
def table(verbose):
    """Show LLDP neighbors in tabular format"""
    from show.main import run_command

    cmd = ['sudo', 'lldpshow']
    run_command(cmd, display_cmd=verbose)


@lldp.command("config")
@clicommon.pass_db
def config(db):
    """Show global LLDP configuration from CONFIG_DB"""
    entry = db.cfgdb.get_entry(LLDP_GLOBAL_TABLE, LLDP_GLOBAL_KEY)
    rows = build_global_display_rows(entry)
    click.echo(tabulate(rows, headers=["Parameter", "Value"], tablefmt="simple"))


@lldp.command("interfaces")
@clicommon.pass_db
def interfaces(db):
    """Show per-interface LLDP configuration from CONFIG_DB"""
    port_table = db.cfgdb.get_table(LLDP_PORT_TABLE)
    if not port_table:
        click.echo("No per-interface LLDP configuration found")
        return
    header, body = build_port_display_rows(port_table)
    click.echo(tabulate(body, headers=header, tablefmt="simple"))


@lldp.command("interface")
@click.argument("ifname", metavar="<interface_name>", required=True)
@clicommon.pass_db
def interface(db, ifname):
    """Show LLDP configuration for an interface from CONFIG_DB"""
    ctx = click.get_current_context()
    from config.main import interface_name_is_valid
    if interface_name_is_valid(db.cfgdb, ifname) is False:
        ctx.fail("Interface name is invalid. Please enter a valid interface name!!")

    entry = db.cfgdb.get_entry(LLDP_PORT_TABLE, ifname)
    if not entry:
        click.echo("No LLDP configuration found for {}".format(ifname))
        return
    header, body = build_port_display_rows({ifname: entry}, ifname=ifname)
    click.echo(tabulate(body, headers=header, tablefmt="simple"))


@lldp.command("custom-tlv")
@clicommon.pass_db
def custom_tlv(db):
    """Show advertised custom LLDP TLVs from CONFIG_DB"""
    table = db.cfgdb.get_table(LLDP_CUSTOM_TLV_TABLE)
    if not table:
        click.echo("No LLDP custom TLVs configured")
        return
    header, body = build_custom_tlv_display_rows(table)
    click.echo(tabulate(body, headers=header, tablefmt="simple"))


@lldp.command("statistics")
@click.argument("interfacename", required=False)
@clicommon.pass_db
def statistics(db, interfacename):
    """Show LLDP statistics from COUNTERS_DB"""
    if interfacename is not None and clicommon.get_interface_naming_mode() == "alias":
        from show.main import iface_alias_converter
        interfacename = iface_alias_converter.alias_to_name(interfacename)

    entries = collect_lldp_statistics(db.db, interfacename)
    if not entries:
        if interfacename:
            click.echo("No LLDP statistics found for {}".format(interfacename))
        else:
            click.echo("No LLDP statistics found")
        return

    header, body = build_statistics_display_rows(entries)
    click.echo(tabulate(body, headers=header, tablefmt="simple"))
