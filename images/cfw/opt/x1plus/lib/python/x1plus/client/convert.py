import json, yaml
import zlib
import base64
import sys

def _cmd_convert(args):
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
    elif args.b64:
        try:
            value = base64.b64decode(value, validate=True)
        except Exception as e:
            print(f"value did not look like valid base64 to me: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            value = zlib.decompress(value)
        except Exception as e:
            print(f"value did not look like valid zlib stream inside of base64 to me: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            value = json.loads(value)
        except Exception as e:
            print(f"value did not look like valid JSON inside of zlib inside of base64 to me: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Well, let's try some stuff.
        try:
            zvalue = base64.b64decode(value, validate=True)
            zvalue = zlib.decompress(zvalue)
            value = json.loads(zvalue)
        except:
            try:
                # This will catch things that look like numbers, and quoted strings, and, of course, actual honest-to-god JSON.
                value = json.loads(value)
            except:
                try:
                    value = yaml.safe_load(value)
                except:
                    print(f"'{value}' could not be parsed as either JSON or YAML or X1Plus Gcode action", file=sys.stderr)
                    sys.exit(1)
    
    if args.to is None or args.to[0] == 'b64':
        print(base64.b64encode(zlib.compress(json.dumps(value).encode(), 9)).decode())
    elif args.to[0] == 'json':
        print(json.dumps(value, indent=4))
    elif args.to[0] == 'yaml':
        print(yaml.dump(value))
    else:
        print(f"unsupported output format {args.to[0]} (try 'b64', 'json', 'yaml')", file=sys.stderr)
        sys.exit(1)

def add_subparser(subparsers):
    parser = subparsers.add_parser('convert', help="convert between various action and configuration formats")
    parser.add_argument('action', action="store", nargs=1, help="string (or file) to convert (defaults to 'generous' parsing, can be overridden with individual parse options)")
    parser.add_argument('--json', action="store_true", help="strictly interpret value as JSON")
    parser.add_argument('--yaml', action="store_true", help="interpret value as YAML")
    parser.add_argument('--b64', action="store_true", help="interpret value as X1Plus G-code format (b64zjson)")
    parser.add_argument('--file', action="store_true", help="take input from a file")
    parser.add_argument('--to', action="store", nargs=1, help="format to convert to (options are json, yaml, b64; defaults to b64)")
    parser.set_defaults(func=_cmd_convert)
    