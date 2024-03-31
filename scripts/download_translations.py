#!/usr/bin/env python3
import requests
import sys

# python3 -m pip install crowdin-api-client
from crowdin_api import CrowdinClient

# read-only token ... safe to commit to the repo
TOKEN = (
    "c4b3b8f8338e799ab1e0184573e4d7505517810625260313e97e5e66011482d2443e216215ee74e0"
)
PROJECT_ID = 659058

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

with open(sys.argv[1], 'wb') as f:
    f.write(req.content)

print(f"wrote {sys.argv[1]}")
