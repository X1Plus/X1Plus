from .base import call

from jeepney import DBusAddress

ACTIONS_DBUS_ADDRESS = DBusAddress('/x1plus/actions', bus_name='x1plus.x1plusd', interface='x1plus.actions')

def execute(action):
    return call(ACTIONS_DBUS_ADDRESS, 'Execute', action)

###

import json, yaml

def _cmd_execute(args):
    value = args.action[0]
    
    if args.file:
        if value[-5:] == ".json":
            args.json = True
        if value[-5:] == ".yaml" or value[-4:] == ".yml":
            args.yaml = True
        with open(value) as f:
            value = f.read()

    if args.yaml:
        try:
            value = yaml.safe_load(value)
        except Exception as e:
            print(f"'{value}' does not look like valid YAML to me: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.json:
        try:
            value = json.loads(value)
        except Exception as e:
            print(f"'{value}' does not look like valid JSON to me: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Well, let's try some stuff.
        try:
            # This will catch things that look like numbers, and quoted strings, and, of course, actual honest-to-god JSON.
            value = json.loads(value)
        except:
            try:
                value = yaml.safe_load(value)
            except:
                print(f"'{value}' could not be parsed as either JSON or YAML", file=sys.stderr)
    
    print("executing action:")
    print(json.dumps(value, indent=4))
    execute(value)

def add_subparser(subparsers):
    parser = subparsers.add_parser('action', help="execute an X1Plus action")
    
    parser.add_argument('action', action="store", nargs=1, help="action (or file) to run (defaults to 'generous' parsing, can be overridden with individual parse options)")
    parser.add_argument('--json', action="store_true", help="strictly interpret value as JSON")
    parser.add_argument('--yaml', action="store_true", help="interpret value as YAML")
    parser.add_argument('--file', action="store_true", help="take input from a file")
    parser.set_defaults(func=_cmd_execute)
