#!/usr/bin/env bash
if [ ! -f ../../latest.x1p ] ; then
    echo "latest.x1p is missing, please create a symlink first."
    exit 1
fi
echo "Removing old build directory"
rm -rf out
echo "Taking care of dependencies"
npm i
echo "Building installers"
npm run package -- -p win32,darwin,linux || exit $?
cd out || exit 1
echo "Creating installer archives"
zip -q -r install-gui-win32-x64.zip 'X1Plus Installer-win32-x64'
tar czf install-gui-linux-x64.tar.gz 'X1Plus Installer-linux-x64'
tar czf install-gui-darwin-x64.tar.gz 'X1Plus Installer-darwin-x64'
