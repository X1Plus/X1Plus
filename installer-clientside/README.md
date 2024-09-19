# Building the installer

This is sort of a mess, but at least it's in a script now. If you understand
Node release engineering I want to hear from you. Actually I don't, I just want
a PR for it. Thanks.

Make sure the user running the following command is a member of the docker
group. Running with `sudo` will result in dubious ownership errors, so the
script will exit if you try to do so.
```./build.sh```

The output files should then be found in `install-gui/out/`

# Local MQTT test server

Under `install-gui`, you can run `npm run mqtt-serve` to do quick tests with 
a dummy MQTT server, requires `mosquitto` and its utilities (`mosquitto-clients` 
on Ubuntu).