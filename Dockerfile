# Copyright (C) 2020 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


FROM ubuntu:focal

RUN apt update && apt install -y git sudo
RUN git clone https://github.com/ahamilton/eris
RUN cd eris && git checkout afa6870484e50ad4ba7b8d662c4ed708c29a759b
RUN rm -rf eris/.git
RUN DEBIAN_FRONTEND=noninteractive apt install -y tzdata
RUN cd eris && ./install-dependencies
RUN python3.8 -m pip install ./eris

ENTRYPOINT ["eris"]
