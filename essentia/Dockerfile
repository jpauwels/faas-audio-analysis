FROM alpine:3.19 AS builder

RUN apk add --no-cache build-base eigen-dev yaml-dev python3-dev py3-numpy-dev qt5-qtbase-dev swig zlib-dev fftw-dev ffmpeg4-dev libsamplerate-dev taglib-dev chromaprint-dev git

ARG GAIA_COMMIT=0d0942bf4748b40069977702715454ae084063c9
RUN wget https://github.com/MTG/gaia/archive/${GAIA_COMMIT}.zip \
 && unzip ${GAIA_COMMIT}.zip \
 && rm ${GAIA_COMMIT}.zip \
 && cd gaia-${GAIA_COMMIT} \
 && python3 waf configure --with-tests --with-python-bindings \
 && python3 waf \
 && python3 waf install \
 && cd .. \
 && rm -rf gaia-${GAIA_COMMIT}

ARG ESSENTIA_COMMIT=1d1cc983e9b30a040b0563184344950effc532b4
RUN git clone https://github.com/MTG/essentia.git \
 && cd essentia \
 && git checkout ${ESSENTIA_COMMIT} \
 && python3 waf configure --build-static --with-examples --with-python --with-cpptests --with-vamp --with-gaia \
 && python3 waf install \
 && cd .. \
 && rm -rf essentia


FROM alpine:3.19

RUN apk add --no-cache \
    yaml \
    python3 \
    py3-numpy \
    qt5-qtbase \
    fftw \
    ffmpeg \
    ffmpeg4 \
    ffmpeg4-libavcodec \
    ffmpeg4-libavformat \
    ffmpeg4-libswresample \
    libsamplerate \
    taglib \
    chromaprint-libs \
    py3-pip

COPY --from=builder /usr/local/bin/essentia_* /usr/local/bin/
COPY --from=builder /usr/local/include/essentia/ /usr/local/include/essentia/
COPY --from=builder /usr/local/lib/pkgconfig/essentia.pc /usr/local/pkgconfig/
COPY --from=builder /usr/local/lib/libessentia.a /usr/local/lib/
COPY --from=builder /usr/local/lib/python3.11/site-packages/essentia/ /usr/lib/python3.11/site-packages/essentia/

# Add non root user
RUN addgroup --system app && adduser app --system --ingroup app --home /home/app && chown app:app /home/app

USER app
ENV PATH=$PATH:/home/app/.local/bin
RUN pip install --user --break-system-packages fastapi[standard]

WORKDIR /home/app/function
COPY --chown=app:app entrypoint.py .
COPY --chown=app:app run-essentia.sh .
WORKDIR /tmp

CMD ["fastapi", "run", "--port", "5000", "/home/app/function/entrypoint.py"]
EXPOSE 5000
