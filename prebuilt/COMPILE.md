# Cross Compile Documentation

This expects you to have the docker file made already, and to use it for compiling.
```
docker build -t x1plusbuild scripts/docker/
docker run -it -v `pwd`:/work:Z x1plusbuild
```

## Compile of pv (autoconf)
```
cd ~
git clone https://github.com/icetee/pv.git
cd pv
export PATH=/opt/gcc-arm-8.3-2019.03-x86_64-arm-linux-gnueabihf/bin:${PATH}
export LDFLAGS="-s -w"
./configure --build=x86_64-linux-gnu --host=arm-linux-gnueabihf --target=arm-linux-gnueabihf
make -j`nproc` LD="arm-linux-gnueabihf-ld" # pv needs LD set, according to buildroot makefile
cp pv /work/images/cfw/usr/bin/pv
chmod +x /work/images/cfw/usr/bin/pv
exit
```

## Compile of jq (autoconf)
```
cd ~
git clone https://github.com/jqlang/jq.git
cd jq
export PATH=/opt/gcc-arm-8.3-2019.03-x86_64-arm-linux-gnueabihf/bin:${PATH}
export LDFLAGS="-s -w"
git submodule update --init
autoreconf -i
./configure --build=x86_64-linux-gnu --host=arm-linux-gnueabihf --target=arm-linux-gnueabihf
make -j`nproc`
cp jq /work/images/cfw/usr/bin/jq
chmod +x /work/images/cfw/usr/bin/jq
exit
```
