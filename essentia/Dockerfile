FROM alpine:3.8 as builder

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
RUN git clone https://github.com/acoustid/chromaprint.git
RUN cd chromaprint && mkdir build && cd build && cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TOOLS=ON -DFFT_LIB=fftw3 .. && make install
# RUN git clone https://github.com/MTG/gaia.git
# RUN echo "http://dl-cdn.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories && apk update --no-cache
RUN git clone https://github.com/jpauwels/gaia.git
RUN apk add --no-cache qt-dev #swig libtbb-dev
RUN cd gaia && python3 waf configure && python3 waf && python3 waf install # --with-tbb --with-python-bindings
RUN git clone https://github.com/MTG/essentia.git
RUN cd essentia && git checkout 133a0d3f9a14663fdd22c9dad24445998cbb8aae && python3 waf configure --build-static --with-examples --with-python  --with-gaia --with-vamp --with-cpptests \
&&  python3 waf install


FROM alpine:3.8

RUN apk add --no-cache \
    fftw \
    ffmpeg \
    libsamplerate \
    taglib \
    yaml \
    py3-numpy \
    py3-six
RUN apk add --no-cache qt

COPY --from=builder /usr/local/bin/essentia_* /usr/local/bin/
COPY --from=builder /usr/local/include/essentia/ /usr/local/include/essentia/
COPY --from=builder /usr/local/lib/libchromaprint* /usr/local/lib/
COPY --from=builder /usr/local/lib/pkgconfig/libchromaprint.pc /usr/local/pkgconfig/
COPY --from=builder /usr/local/lib/libessentia.a /usr/local/lib/
COPY --from=builder /usr/local/lib/pkgconfig/essentia.pc /usr/local/pkgconfig/
COPY --from=builder /usr/local/lib/python3.6/site-packages/essentia/ /usr/lib/python3.6/site-packages/essentia/

# /usr/local/lib/pkgconfig/libchromaprint.pc
# -- Installing: /usr/local/lib/libchromaprint.so.1.4.4
# -- Installing: /usr/local/lib/libchromaprint.so.1
# -- Installing: /usr/local/lib/libchromaprint.so
# -- Installing: /usr/local/include/chromaprint.h
# -- Installing: /usr/local/bin/fpcalc

RUN apk add --no-cache curl \
&&  echo "Pulling watchdog binary from Github." \
&&  curl -sSL https://github.com/openfaas/faas/releases/download/0.9.6/fwatchdog > /usr/bin/fwatchdog \
&&  chmod +x /usr/bin/fwatchdog \
&&  apk del --no-cache curl


# Add non root user
RUN addgroup -S app && adduser app -S -G app
RUN chown app /home/app
WORKDIR /home/app
USER app

COPY entrypoint.sh .

# Populate example here - i.e. "cat", "sha512sum" or "node index.js"
ENV fprocess="xargs ./entrypoint.sh"
# Set to true to see request in function logs
ENV write_debug="false"

EXPOSE 8080

HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1
CMD [ "fwatchdog" ]
