from .base import call

from jeepney import DBusAddress

SETTINGS_DBUS_ADDRESS = DBusAddress('/x1plus/settings', bus_name='x1plus.x1plusd', interface='x1plus.settings')

_settings = None

def get_settings(force = False):
    global _settings
    if _settings == None or force:
        _settings = call(SETTINGS_DBUS_ADDRESS, 'GetSettings')
    return _settings

def get():
    return get_settings().get(*args)

def put_multiple(keys):
    return call(SETTINGS_DBUS_ADDRESS, 'PutSettings', keys)

def put(key, value):
    put_multiple({ key: value })

###

import json, yaml, sys, pathlib

# multiline strings, like gcode, should be clearer about what they do when we dump them
def str_representer(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)
yaml.add_representer(str, str_representer)

def _cmd_get(args):
    rv = 0
    settings = get_settings()
    settings_to_print = {}
    must_print_names = False
    if len(args.keys) == 0:
        settings_to_print = settings

    for key in args.keys:
        if '*' in key:
            must_print_names = True
            didmatch = False
            for k,v in sorted(settings.items()):
                if pathlib.PurePath(k).match(key):
                    didmatch = True
                    settings_to_print[k] = v
            if not didmatch:
                print(f"key {key} had no matches!", file=sys.stderr)
                rv = 1
            continue

        if key not in settings:
            print(f"key {key} is not set!", file=sys.stderr)
            rv = 1
        else:
            settings_to_print[key] = settings[key]

    if len(settings_to_print) == 1 and not must_print_names:
        k,v = settings_to_print.popitem()
        if args.json: # pretty-printed JSON
            print(json.dumps(v, indent=4))
        elif args.yaml:
            print(yaml.dump(v))
        else:
            print(json.dumps(v))
    else:
        if args.json:
            print(json.dumps(settings_to_print, indent=4))
        elif args.yaml:
            print(yaml.dump(settings_to_print))
        else:
            for k,v in sorted(settings_to_print.items()):
                print(f"{k}: {json.dumps(v)}")

    sys.exit(rv) 

def _cmd_set(args):
    value = args.value[0]
    
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
    elif args.number:
        try:
            try:
                value = int(value)
            except:
                value = float(value)
        except Exception as e:
            print(f"'{value}' does not look like a number to me: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.string:
        pass # well, it already is
    elif args.bool:
        if value.lower() == "true" or value.lower() == "yes" or value.lower() == "1":
            value = True
        elif value.lower() == "false" or value.lower() == "no" or value.lower() == "0":
            value = False
        else:
            print(f"'{value}' does not look like a boolean to me", file=sys.stderr)
            sys.exit(1)
    elif args.null:
        if value == "" or value.lower() == "none" or value.lower() == "null" or value.lower() == "0":
            value = None
        else:
            print(f"'{value}' ain't no null I ever heard of.  they speak Python in '{value}'?", file=sys.stderr)
            sys.exit(1)
    else:
        # Well, let's try some stuff.
        try:
            # This will catch things that look like numbers, and quoted strings, and, of course, actual honest-to-god JSON.
            value = json.loads(value)
        except:
            # Ok, maybe something boolean-ish?
            if value.lower() == "true" or value.lower() == "yes":
                value = True
            elif value.lower() == "false" or value.lower() == "no":
                value = False
            # Or something nullish?
            elif value == "" or value.lower() == "null":
                value = None
            else:
                # No idea.  I guess it's a string.
                pass

    put(args.key[0], value)
    print(f"{args.key[0]}: {json.dumps(value)}")

def add_subparser(subparsers):
    parser = subparsers.add_parser('settings', help="manage X1Plus settings")
    settings_subparsers = parser.add_subparsers(title = 'subcommands', required = True)

    get_parser = settings_subparsers.add_parser('get', help='print one or more X1Plus settings', aliases=['show'])
    get_parser.add_argument('keys', action="store", nargs="*", help="zero or more setting keys to look up; if not specified, prints all settings")
    get_parser.add_argument('--json', action="store_true", help="dump settings as JSON")
    get_parser.add_argument('--yaml', action="store_true", help="dump settings as YAML")
    get_parser.set_defaults(func=_cmd_get)
    
    # XXX: should there be a 'known' option that shows all known settings?
    
    set_parser = settings_subparsers.add_parser('set', help='write an X1Plus setting')
    set_parser.add_argument('key', action="store", nargs=1, help="name of the setting key to write")
    set_parser.add_argument('value', action="store", nargs=1, help="value to write (defaults to 'generous' parsing, can be overridden with individual parse options)")
    set_parser.add_argument('--json', action="store_true", help="strictly interpret value as JSON")
    set_parser.add_argument('--yaml', action="store_true", help="interpret value as YAML")
    set_parser.add_argument('--file', action="store_true", help="take input from a file")
    set_parser.add_argument('--number', action="store_true", help="strictly interpret value as a number")
    set_parser.add_argument('--string', action="store_true", help="strictly interpret value as a string")
    set_parser.add_argument('--bool', action="store_true", help="strictly interpret value as a boolean")
    set_parser.add_argument('--null', action="store_true", help="strictly interpret value as a null")
    set_parser.set_defaults(func=_cmd_set)
