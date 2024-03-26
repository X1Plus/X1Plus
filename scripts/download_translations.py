#!/usr/bin/env python3
import zipfile
import requests
import io
import json
import os
import xml.etree.ElementTree as ET

# python3 -m pip install crowdin-api-client
from crowdin_api import CrowdinClient

# read-only token ... safe to commit to the repo
TOKEN = (
    "c4b3b8f8338e799ab1e0184573e4d7505517810625260313e97e5e66011482d2443e216215ee74e0"
)
PROJECT_ID = 659058

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

client = CrowdinClient(
    token=TOKEN,
    project_id=PROJECT_ID,
)

builds = client.translations.list_project_builds()
latestbuild = sorted(
    (b for b in builds["data"] if b["data"]["status"] == "finished"),
    key=lambda d: d["data"]["createdAt"],
)[-1]["data"]

print(f"downloading latest build {latestbuild}")
download = client.translations.download_project_translations(buildId=latestbuild["id"])
req = requests.get(download["data"]["url"])

archive = zipfile.ZipFile(io.BytesIO(req.content))

# Unpack each language and update as needed.
build_ver = int(latestbuild["createdAt"].strftime("%Y%m%d%H%M"))

for lang in LANG_MAP:
    print(f"unpacking {lang}...")

    jsonlang = LANG_MAP[lang][1]

    for src in ["hms_texts", "error_texts"]:
        ts_tree = ET.fromstring(archive.open(f"{lang}/{src}.ts").read())

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
