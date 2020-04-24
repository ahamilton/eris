# Copyright (C) 2020 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


FROM ubuntu:eoan

RUN apt update && apt install -y git sudo
RUN git clone https://github.com/ahamilton/eris
RUN cd eris && git checkout b696c65f4cec1ae53a3d49352dd1380a6a8f9510
RUN rm -rf eris/.git
RUN DEBIAN_FRONTEND=noninteractive apt install -y tzdata
RUN cd eris && ./install-dependencies
RUN python3.8 -m pip install ./eris

ENTRYPOINT ["eris"]
