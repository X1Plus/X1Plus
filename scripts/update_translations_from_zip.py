#!/usr/bin/env python3

import zipfile
import xml.etree.ElementTree as ET
import json
import os
import sys
import io

from collections import namedtuple

TranslatableLanguage = namedtuple('LangMapEnt', ['crowdin_language', 'crowdin_ts_dir', 'tslang', 'jsonlang'])

# crowdin language -> (base.tsapp_*.ts, error_texts.*.json)
LANG_MAP = [
    TranslatableLanguage('de', 'de-DE', 'de', 'de'),
    TranslatableLanguage('en', 'en-US', 'en', 'en'),
    TranslatableLanguage('es-ES', 'es-ES', 'es', 'es'),
    TranslatableLanguage('fr', 'fr-FR', 'fr', 'fr'),
    TranslatableLanguage('ja', 'ja-JP', 'ja', 'ja'),
    TranslatableLanguage('nl', 'nl-NL', 'nl', 'nl'),
    TranslatableLanguage('ru', 'ru-RU', 'ru', 'ru'),
    TranslatableLanguage('pt-PT', 'pt-PT', 'pt', 'pt'),
    TranslatableLanguage('tr', 'tr-TR', 'tr', 'tr'),
    TranslatableLanguage('sv-SE', 'sv-SE', 'sv', 'sv'),
    TranslatableLanguage('zh-CN', 'zh-CN', 'cn', 'zh-cn'),
    TranslatableLanguage('zh-TW', 'zh-TW', 'tw', 'zh-tw'),
]

archive = zipfile.ZipFile(sys.argv[1])

# Unpack each language and update as needed.
dt = archive.getinfo("en-US/Firmware/base.ts").date_time
build_ver = int(f"{dt[0]:04d}{dt[1]:02d}{dt[2]:02d}{dt[3]:02d}{dt[4]:02d}")

for lang in LANG_MAP:
    print(f"unpacking {lang}...")


    for src in ["hms_texts", "error_texts"]:
        ts_tree = ET.fromstring(archive.open(f"{lang.crowdin_language}/Firmware/{src}.ts").read())

        # jsonlang = 'en' translations always seem to be 'unfinished', so
        # take the ones from CrowdIn anyway
        messages = {
            m.get("id"): m.find("./translation").text or ""
            for m in ts_tree.iter("message")
            if (
                lang.jsonlang == "en"
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
                    f"{src}.{lang.jsonlang}.json",
                ),
                "r",
            ) as f:
                orig = json.load(f)[lang.jsonlang]
        except:
            print(f"did not find original {src}.{lang.jsonlang}.json")
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
                f"language {lang.jsonlang} {src} has ecodes {missing_from_db} missing from database... very curious"
            )

        # new codes that we need to append
        for ecode in set(messages.keys()) - set(msg["ecode"] for msg in orig):
            newmsgs.append({"ecode": ecode, "intro": messages[ecode]})

        contents = {lang.jsonlang: newmsgs, "ver": build_ver}
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "bbl_screen-patch",
                "printer_ui",
                "printerui",
                "text",
                f"{src}.{lang.jsonlang}.json",
            ),
            "w",
        ) as f:
            json.dump(contents, f, indent=4, ensure_ascii=False)

    # the tricky one is base.ts.  we need to take the on disk one, and do an
    # in-order merge with the output from CrowdIn, in a
    # whitespace-preserving way (ugh) so that we can properly diff against
    # BBL lconvert-generated .ts files.  gross.  actually, it is sort of
    # like the json situation, but...  xml.
    new_tree = ET.fromstring(
        ET.canonicalize(archive.open(f"{lang.crowdin_ts_dir}/Firmware/base.ts").read())
    )
    try:
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "bbl_screen-patch",
                "printer_ui-orig",
                "printerui",
                f"app_{lang.tslang}.ts",
            ),
            "r",
        ) as f:
            old_tree = ET.fromstring(f.read())
    except:
        print(f"did not find original app_{lang.tslang}.ts")
        old_tree = new_tree

    # which contexts are missing?  just append them
    ctxsnew = {ctx.find("name").text for ctx in new_tree.findall("./context")}
    ctxsold = {ctx.find("name").text for ctx in old_tree.findall("./context")}

    def stripmsg(msgnew):
        msgold = ET.Element("message")
        if msgnew.get("id"):
            msgold["id"] = msgnew["id"]
        msgold.append(msgnew.find("./source"))
        msgold.append(msgnew.find("./translation"))
        return msgold

    for ctxname in ctxsnew - ctxsold:
        ctxnew = new_tree.find(f"./context/name[.='{ctxname}']..")
        ctxold = ET.Element("context")
        namese = ET.SubElement(ctxold, "name")
        namese.text = ctxname
        hasmsg = False
        for msgnew in ctxnew.findall("./message"):
            if msgnew.find("./translation").get("type", "") == "unfinished":
                continue
            ctxold.append(stripmsg(msgnew))
            hasmsg = True
        ctxold.tail = "\n"
        ET.indent(ctxold)
        if hasmsg:
            old_tree.append(ctxold)

    # now update all original contexts
    for ctxname in ctxsold:
        ctxold = old_tree.find(f"./context/name[.='{ctxname}']..")
        ctxnew = new_tree.find(f"./context/name[.='{ctxname}']..")
        if not ctxnew:
            print(f"context {ctxname} missing from ctxnew?")
            continue
        # O(m*n)... woof
        # probably we should match by message.id too, but...
        for msgnew in ctxnew.findall("./message/translation[@type!='unfinished'].."):
            trnew = msgnew.find("./translation")
            if not trnew:
                continue
            srcnew = msgnew.find("./source").text
            found = False
            for msgold in ctxold.findall("./message"):
                if msgold.find("./source").text == srcnew:
                    trold = msgold.find("./translation")
                    trold.text = trnew.text
                    trold.attrib = trnew.attrib
                    found = True
                    break
            if not found:
                ctxold.append(stripmsg(msgnew))

    # and spit it out
    with open(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "bbl_screen-patch",
            "printer_ui",
            "printerui",
            f"app_{lang.tslang}.ts",
        ),
        "w",
    ) as f:
        f.write(ET.canonicalize(ET.tostring(old_tree, encoding="utf-8")))
