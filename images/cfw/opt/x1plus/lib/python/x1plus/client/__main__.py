import argparse
from . import ota, settings

"""
Basic command-line X1Plus management tool.
"""

parser = argparse.ArgumentParser(prog='x1plus', description='Command-line management tool for X1Plus')
subparsers = parser.add_subparsers(title = 'commands', required = True)

ota.add_subparser(subparsers)
settings.add_subparser(subparsers)

args = parser.parse_args()
args.func(args)