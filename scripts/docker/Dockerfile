FROM ubuntu:22.04

RUN apt-get update && apt-get -y install curl wget xz-utils

RUN wget -O /tmp/gcc-arm-8.3-2019.03-x86_64-arm-linux-gnueabihf.tar.xz 'https://developer.arm.com/-/media/Files/downloads/gnu-a/8.3-2019.03/binrel/gcc-arm-8.3-2019.03-x86_64-arm-linux-gnueabihf.tar.xz?revision=e09a1c45-0ed3-4a8e-b06b-db3978fd8d56&rev=e09a1c450ed34a8eb06bdb3978fd8d56&hash=EFF6A5D00F2F48194BA9FF99EF044990BE996BE0' && \
    mkdir -p /opt && \
    tar xJvf /tmp/gcc-arm-8.3-2019.03-x86_64-arm-linux-gnueabihf.tar.xz -C /opt && \
    rm /tmp/gcc-arm-8.3-2019.03-x86_64-arm-linux-gnueabihf.tar.xz

RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash
RUN apt-get install -y nodejs
ENV DEBIAN_FRONTEND="noninteractive" TZ="Etc/UTC"
RUN apt-get update && apt-get -y install sudo build-essential python3 autoconf libtool cpio jq \
    squashfs-tools-ng unzip gcc-multilib python3-pip qtbase5-dev-tools qtdeclarative5-dev qtbase5-dev qttools5-dev-tools && \
    apt-get clean

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 0

ENV LANG=en_US.UTF-8
RUN apt-get install --no-install-recommends -y locales && \
    apt-get clean && \
    locale-gen ${LANG} && update-locale LANG=${LANG}

ENV TOOLCHAIN=/opt/gcc-arm-8.3-2019.03-x86_64-arm-linux-gnueabihf/bin/arm-linux-gnueabihf-
RUN apt-get install -y xdelta3 rsync && apt-get clean
RUN pip3 install pycryptodome unicorn pyelftools
RUN apt-get install -y git && apt-get clean
RUN useradd -m docker && echo "docker:docker" | chpasswd && adduser docker sudo

RUN mkdir -p /work

USER docker
WORKDIR /work
ENV X1PLUS_DOCKER_ENV_VERSION=3
CMD /bin/bash
