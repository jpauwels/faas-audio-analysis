FROM ghcr.io/openfaas/classic-watchdog:0.3.3 AS watchdog

FROM alpine:3.15 AS builder

RUN apk add --no-cache build-base eigen-dev yaml-dev python3-dev py3-numpy-dev qt5-qtbase-dev swig libtbb-dev git zlib-dev fftw-dev ffmpeg-dev libsamplerate-dev taglib-dev chromaprint-dev
RUN wget https://github.com/MTG/gaia/archive/refs/heads/master.zip \
 && unzip master.zip \
 && rm master.zip \
 && cd gaia-master \
 && python3 waf configure --with-tests --with-python-bindings --with-tbb \
 && python3 waf \
 && python3 waf install \
 && cd .. \
 && rm -rf gaia-master
RUN git clone https://github.com/MTG/essentia.git \
 && cd essentia \
 && git checkout 1d1cc983e9b30a040b0563184344950effc532b4 \
 && CPATH=/usr/include/eigen3 python3 waf configure --build-static --with-examples --with-python --with-cpptests --with-vamp --with-gaia \
 && python3 waf install \
 && cd .. \
 && rm -rf essentia


FROM alpine:3.15

COPY --chmod=755 --from=watchdog /fwatchdog /usr/bin/fwatchdog

RUN apk add --no-cache \
    yaml \
    python3 \
    py3-numpy \
    qt5-qtbase \
    libtbb \
    fftw \
    ffmpeg \
    libsamplerate \
    taglib \
    chromaprint \
    libtbb \
    py3-pip

COPY --from=builder /usr/local/bin/essentia_* /usr/local/bin/
COPY --from=builder /usr/local/include/essentia/ /usr/local/include/essentia/
COPY --from=builder /usr/local/lib/pkgconfig/essentia.pc /usr/local/pkgconfig/
COPY --from=builder /usr/local/lib/libessentia.a /usr/local/lib/
COPY --from=builder /usr/local/lib/python3.9/site-packages/essentia/ /usr/lib/python3.9/site-packages/essentia/

# Add non root user
RUN addgroup --system app && adduser app --system --ingroup app --home /home/app && chown app:app /home/app
WORKDIR /home/app

COPY --chown=app:app openfaas_entrypoint.sh openfaas_entrypoint.sh
COPY --chown=app:app run-essentia.sh run-essentia.sh
WORKDIR /tmp
USER app

# Populate example here - i.e. "cat", "sha512sum" or "node index.js"
ENV fprocess="/home/app/openfaas_entrypoint.sh"
EXPOSE 8080
HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1
CMD ["fwatchdog"]
