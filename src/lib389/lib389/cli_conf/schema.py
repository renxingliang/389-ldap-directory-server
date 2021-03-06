# --- BEGIN COPYRIGHT BLOCK ---
# Copyright (C) 2016, William Brown <william at blackhats.net.au>
# All rights reserved.
#
# License: GPL (version 3 or any later version).
# See LICENSE for details.
# --- END COPYRIGHT BLOCK ---

from lib389.cli_base import _get_arg
from lib389.schema import Schema


def list_attributetype(inst, basedn, log, args):
    for attributetype in inst.schema.get_attributetypes():
        print(attributetype)

def query_attributetype(inst, basedn, log, args):
    # Need the query type
    attr = _get_arg(args.attr, msg="Enter attribute to query")
    attributetype, must, may = inst.schema.query_attributetype(attr)
    print(attributetype)
    print("")
    print("MUST")
    for oc in must:
        print(oc)
    print("")
    print("MAY")
    for oc in may:
        print(oc)

def reload_schema(inst, basedn, log, args):
    schema = Schema(inst)
    log.info('Attempting to add task entry... This will fail if Schema Reload plug-in is not enabled.')
    task = schema.reload(args.schemadir)
    log.info('Successfully added task entry ' + task.dn)
    log.info("To verify that the schema reload operation was successful, please check the error logs.")


def create_parser(subparsers):
    schema_parser = subparsers.add_parser('schema', help='Query and manipulate schema')

    subcommands = schema_parser.add_subparsers(help='schema')

    list_attributetype_parser = subcommands.add_parser('list_attributetype', help='List avaliable attribute types on this system')
    list_attributetype_parser.set_defaults(func=list_attributetype)

    query_attributetype_parser = subcommands.add_parser('query_attributetype', help='Query an attribute to determine object classes that may or must take it')
    query_attributetype_parser.set_defaults(func=query_attributetype)
    query_attributetype_parser.add_argument('attr', nargs='?', help='Attribute type to query')

    reload_parser = subcommands.add_parser('reload', help='Dynamically reload schema while server is running')
    reload_parser.set_defaults(func=reload_schema)
    reload_parser.add_argument('-d', '--schemadir', help="directory where schema files are located")
