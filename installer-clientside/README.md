# Building the installer

This is sort of a mess. Make sure to do things in exactly this order. Otherwise
things will go wrong. If you understand Node release engineering I want to hear
from you. Actually I don't, I just want a PR for it. Thanks. Make sure to build
the docker image first.

* ```docker run -u `id -u` -v `pwd`:/work x1plusbuild bash -c 'cd installer-clientside/x1p-js && npm i && npm run build'```
* ```docker run -u `id -u` -v `pwd`:/work x1plusbuild bash -c 'make && ln -s "$(jq -r '.cfwVersion' ota.json).x1p" latest.x1p'```
* ```docker run -u `id -u` -v `pwd`:/work x1plusbuild bash -c 'cd installer-clientside/install-gui && npm i && bash pack-em-all.sh'```

# Local MQTT test server

Under `install-gui`, you can run `npm run mqtt-serve` to do quick tests with 
a dummy MQTT server, requires `mosquitto` and its utilities (`mosquitto-clients` 
on Ubuntu).