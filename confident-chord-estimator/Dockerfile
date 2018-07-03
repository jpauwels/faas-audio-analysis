FROM ubuntu:18.04

RUN apt-get update -y \
&&  apt-get install -y build-essential python3 python3-pip ffmpeg git \
&&  apt-get clean \
&&  rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/app
WORKDIR /home/app
COPY index.py index.py
COPY function /home/app/function/

RUN pip3 install --no-cache-dir -r function/requirements.txt
# RUN pip3 install --no-cache-dir madmom # v0.15.1 in PyPI not working
RUN apt-get update -y \
&&  apt-get install -y git \
&&  git clone --recursive https://github.com/CPJKU/madmom.git \
&&  cd madmom \
&&  python3 setup.py install \
&&  cd .. \
&&  rm -rf madmom \
&&  apt-get purge -y git \
&&  apt-get clean \
&&  rm -rf /var/lib/apt/lists/*

ADD https://github.com/openfaas/faas/releases/download/0.8.0/fwatchdog /usr/bin
RUN chmod +x /usr/bin/fwatchdog

# Add non root user
RUN addgroup --system app && adduser --system --ingroup app app
RUN chown app /home/app
RUN chown -R app:app ./
USER app

# Populate example here - i.e. "cat", "sha512sum" or "node index.js"
ENV fprocess="python3 index.py"
HEALTHCHECK --interval=1s CMD [ -e /tmp/.lock ] || exit 1
CMD [ "fwatchdog" ]
