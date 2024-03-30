#!/usr/bin/env python3

import zipfile
import xml.etree.ElementTree as ET
import json
import os
import sys

# crowdin language -> (app_*.ts, error_texts.*.json)
LANG_MAP = {
    "de": ("de", "de"),
    "en": ("en", "en"),
    "es-ES": ("es", "es"),
    "fr": ("fr", "fr"),
    "ja": ("ja", "ja"),
    "nl": ("nl", "nl"),
    "sv-SE": ("sv", "sv"),
    "zh-CN": ("cn", "zh-cn"),
    "zh-TW": ("tw", "zh-tw"),
}

archive = zipfile.ZipFile(sys.argv[1])

# Unpack each language and update as needed.
dt = archive.getinfo("en/Firmware/base.ts").date_time
build_ver = int(f"{dt[0]:04d}{dt[1]:02d}{dt[2]:02d}{dt[3]:02d}{dt[4]:02d}")

for lang in LANG_MAP:
    print(f"unpacking {lang}...")

    jsonlang = LANG_MAP[lang][1]

    for src in ["hms_texts", "error_texts"]:
        ts_tree = ET.fromstring(archive.open(f"{lang}/Firmware/{src}.ts").read())

        # jsonlang = 'en' translations always seem to be 'unfinished', so
        # take the ones from CrowdIn anyway
        messages = {
            m.get("id"): m.find("./translation").text or ""
            for m in ts_tree.iter("message")
            if (
                jsonlang == "en"
                or m.find("./translation").get("type", None) != "unfinished"
            )
        }

        # we need to merge with the original text in order to keep the diffs
        # small; load it and do that
        try:
            with open(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "bbl_screen-patch",
                    "printer_ui-orig",
                    "printerui",
                    "text",
                    f"{src}.{jsonlang}.json",
                ),
                "r",
            ) as f:
                orig = json.load(f)[jsonlang]
        except:
            print(f"did not find original {src}.{jsonlang}.json")
            orig = []

        newmsgs = []
        for m in orig:
            newmsgs.append(
                {
                    "ecode": m["ecode"],
                    "intro": messages.get(m["ecode"], m["intro"]) or "",
                }
            )

        # does a language have a translation that didn't get uploaded,
        # perhaps because the source key does not exist?
        missing_from_db = set(msg["ecode"] for msg in orig) - set(messages.keys())
        if len(missing_from_db) > 0:
            print(
                f"language {jsonlang} {src} has ecodes {missing_from_db} missing from database... very curious"
            )

        # new codes that we need to append
        for ecode in set(messages.keys()) - set(msg["ecode"] for msg in orig):
            newmsgs.append({"ecode": ecode, "intro": messages[ecode]})

        contents = {jsonlang: newmsgs, "ver": build_ver}
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "bbl_screen-patch",
                "printer_ui",
                "printerui",
                "text",
                f"{src}.{jsonlang}.json",
            ),
            "w",
        ) as f:
            json.dump(contents, f, indent=4, ensure_ascii=False)

    # the tricky one is base.ts.  we need to take the on disk one, and do an
    # in-order merge with the output from CrowdIn, in a
    # whitespace-preserving way (ugh) so that we can properly diff against
    # BBL lconvert-generated .ts files.  gross.
