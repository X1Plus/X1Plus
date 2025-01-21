#! /bin/bash

### THIS ONLY WORKS IF THE USER HAS BEEN ADDED TO THE DOCKER GROUP
### RUNNING THIS WITH `sudo ./build.sh` RESULTS IN DUBIOUS OWNERSHIP
### ERRORS WHEN BUILDING THE FIRMWARE

cd ..
# check if x1plusbuild docker image exists
if ! docker image ls --format '{{.Repository}}' | grep -q '^x1plusbuild$'; then
    echo "x1plusbuild docker image not found, building..."
    docker build -t x1plusbuild scripts/docker/ || exit 1
fi

# build the installer
echo "Building the electron app..."
docker run -u "$(id -u)" -v "$(pwd)":/work x1plusbuild bash -c 'cd installer-clientside/x1p-js && npm i && npm run build' || exit 1

# build the firmware
echo "Building the latest firmware..."
[ -L latest.x1p ] && rm latest.x1p # delete the symlink to the old firmware before building the new one
docker run -u "$(id -u)" -v "$(pwd)":/work x1plusbuild bash -c 'make && ln -s "$(jq -r '.cfwVersion' ota.json).x1p" latest.x1p' || exit 1

# package the installer with the latest build of the firmware
echo "Packaging everything..."
docker run -u "$(id -u)" -v "$(pwd)":/work x1plusbuild bash -c 'cd installer-clientside/install-gui && npm i && bash pack-em-all.sh' || exit 1

cd installer-clientside || exit 1
