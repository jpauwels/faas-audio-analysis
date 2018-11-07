FROM ubuntu:18.04

# Install build dependencies
RUN apt-get update -y \
&&  apt-get install -y build-essential python3 python3-pip ffmpeg git \
&&  apt-get clean \
&&  rm -rf /var/lib/apt/lists/*

# Copy function files
RUN mkdir -p /home/app
WORKDIR /home/app
COPY index.py index.py
COPY function /home/app/function/

# Install Python dependencies
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

# Add watchdog
RUN apt-get update -y \
&&  apt-get install -y curl \
&& curl -sSL https://github.com/openfaas/faas/releases/download/0.9.6/fwatchdog > /usr/bin/fwatchdog \
&& chmod +x /usr/bin/fwatchdog \
&& apt-get autoremove --purge -y curl \
&&  apt-get clean \
&&  rm -rf /var/lib/apt/lists/*

# Add non root user
RUN addgroup --system app && adduser --system --ingroup app app
RUN chown -R app:app ./
USER app

# Populate example here - i.e. "cat", "sha512sum" or "node index.js"
ENV fprocess="python3 index.py"
HEALTHCHECK --interval=1s CMD [ -e /tmp/.lock ] || exit 1
CMD [ "fwatchdog" ]
