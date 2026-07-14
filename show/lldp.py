#
# 'lldp' group ("show lldp ...")
#
# Augments the existing sonic-utilities LLDP show CLI:
#   neighbors / table  - runtime neighbor data via lldpshow (unchanged behavior)
#   config / interfaces / interface - CONFIG_DB settings written by 'config lldp'
#

import click
import utilities_common.cli as clicommon
from natsort import natsorted
from tabulate import tabulate

LLDP_GLOBAL_TABLE = "LLDP"
LLDP_GLOBAL_KEY = "GLOBAL"
LLDP_PORT_TABLE = "LLDP_PORT"

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
