FROM ghcr.io/openfaas/classic-watchdog:0.2.1 as watchdog

FROM alpine:3.9 as builder

RUN apk add --no-cache \
    build-base \
    cmake \
    git \
    python3-dev \
    fftw-dev \
    ffmpeg-dev \
    libsamplerate-dev \
    taglib-dev \
    yaml-dev \
    py3-numpy \
    py-numpy-dev \
    py3-six
RUN git clone --depth 1 https://github.com/acoustid/chromaprint.git
RUN cd chromaprint && mkdir build && cd build && cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TOOLS=ON -DFFT_LIB=fftw3 .. && make install
RUN echo "@main https://dl-cdn.alpinelinux.org/alpine/v3.15/main" >> /etc/apk/repositories && apk update --no-cache
RUN echo "@community https://dl-cdn.alpinelinux.org/alpine/v3.15/community" >> /etc/apk/repositories && apk update --no-cache
RUN apk add --no-cache --allow-untrusted qt-dev eigen-dev@community libtbb-dev@community libucontext@main
RUN git clone --depth 1 https://github.com/MTG/gaia.git
RUN cd gaia && python3 waf configure --with-tbb && python3 waf install
RUN git clone --depth 1 --branch 133a0d3f9a14663fdd22c9dad24445998cbb8aae -c advice.detachedHead=false https://github.com/MTG/essentia.git
RUN cd essentia \
&&  python3 waf configure --build-static --with-examples --with-python --with-gaia --with-vamp --with-cpptests \
&&  python3 waf install


FROM alpine:3.9

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog

RUN apk add --no-cache \
    fftw \
    ffmpeg \
    libsamplerate \
    taglib \
    yaml \
    py3-numpy \
    py3-six \
    bash
RUN echo "@community https://dl-cdn.alpinelinux.org/alpine/v3.15/community" >> /etc/apk/repositories && apk update --no-cache
RUN apk add --no-cache --allow-untrusted qt icu-libs libtbb@community

COPY --from=builder /usr/local/bin/essentia_* /usr/local/bin/
COPY --from=builder /usr/local/bin/fpcalc /usr/local/bin/
COPY --from=builder /usr/local/include/essentia/ /usr/local/include/essentia/
COPY --from=builder /usr/local/include/chromaprint.h /usr/local/include/
COPY --from=builder /usr/local/lib/libchromaprint* /usr/local/lib/
COPY --from=builder /usr/local/lib/pkgconfig/libchromaprint.pc /usr/local/pkgconfig/
COPY --from=builder /usr/local/lib/pkgconfig/essentia.pc /usr/local/pkgconfig/
COPY --from=builder /usr/local/lib/libessentia.a /usr/local/lib/
COPY --from=builder /usr/local/lib/python3.6/site-packages/essentia/ /usr/lib/python3.6/site-packages/essentia/

# Add non root user
RUN addgroup -S app && adduser app -S -G app
WORKDIR /home/app
USER app

COPY openfaas_entrypoint.sh openfaas_entrypoint.sh
COPY run-essentia.sh run-essentia.sh
WORKDIR /tmp

# Populate example here - i.e. "cat", "sha512sum" or "node index.js"
ENV fprocess="/home/app/openfaas_entrypoint.sh"
EXPOSE 8080
HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1
CMD ["fwatchdog"]
