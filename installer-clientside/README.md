# Building the installer

This is sort of a mess, but at least it's in a script now. If you understand
Node release engineering I want to hear from you. Actually I don't, I just want
a PR for it. Thanks.

This will likely only run on macOS or Linux - windows users can install WSL 2
and eventually be able to run this, but that wont be covered here.

If this is the first thing you're running after cloning X1Plus, start by
building the container as described [here](https://github.com/X1Plus/X1Plus?tab=readme-ov-file#how-do-i-get-started)

Make sure the user running the following command is a member of the docker
group. DO NOT USE `sudo`
```./build.sh```

The output files should then be found in `install-gui/out/`

# Local MQTT test server

Under `install-gui`, you can run `npm run mqtt-serve` to do quick tests with 
a dummy MQTT server, requires `mosquitto` and its utilities (`mosquitto-clients` 
on Ubuntu).