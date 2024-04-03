#!/usr/bin/env python3

# Convert the Bambu original error_texts.*.json / hms_texts.*.json to .ts
# files that can then be uploaded to CrowdIn.  Eventually, we will want this
# to merge CrowdIn translations (i.e., downloaded ts files) with possible
# new HMS / Error data, so we keep any corrections of our own and also get
# any new translations.  But for now, we just export it wholesale.
#
# Running this as part of an automated flow is probably a bad idea until it
# can diff ts files.

import json
import sys
import os
import xml.sax.saxutils

def convert(arg, f):
    j = json.load(open(arg, "r"))

    # lol, whatever
    lang = list(set(j.keys()) - {"ver"})[0]

    if "error_texts" in arg:
        contextname = "Errors"
    elif "hms_texts" in arg:
        contextname = "HMS"
    else:
        raise ValueError("invalid filename to translate")

    print(f"converting {contextname} in {lang} from {arg} to {out}")

    f.write('<?xml version="1.0" encoding="utf-8"?>\n')
    f.write("<!DOCTYPE TS>\n")
    f.write(f'<TS version="2.1" language="{lang}" sourcelanguage="en">\n')
    f.write("  <context>\n")
    f.write(f"    <name>{contextname}</name>\n")
    for ent in j[lang]:
        f.write(f"    <message id=\"{ent['ecode']}\">\n")
        outstr = xml.sax.saxutils.escape(ent["intro"])
        if lang == "en":
            f.write(f"      <source>{outstr}</source>\n")
        f.write(f"      <translation>{outstr}</translation>\n")
        f.write("    </message>\n")
    f.write("  </context>\n</TS>\n")

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        with open(os.path.splitext(arg)[0] + ".ts", "w") as f:
            convert(arg, f)
