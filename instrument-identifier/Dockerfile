FROM jpauwels/vampy-instrument-identification

# 1. Use any image as your base image, or "scratch"
# 2. Add fwatchdog binary via https://github.com/openfaas/faas/releases/
# 3. Then set fprocess to the process you want to invoke per request - i.e. "cat" or "my_binary"

ADD https://github.com/openfaas/faas/releases/download/0.8.0/fwatchdog /usr/bin
RUN chmod +x /usr/bin/fwatchdog

# Add non root user
RUN addgroup --system app && adduser --system --ingroup app app
RUN mkdir /home/app/transforms && mv /root/*.n3 /home/app/transforms/ && chown -R app:app /home/app/transforms/*.n3 /usr/local/lib/vamp/*
USER app
WORKDIR /home/app
# RUN pip install --no-cache-dir requests
# COPY ${PWD}/entrypoint.py .

# Populate example here - i.e. "cat", "sha512sum" or "node index.js"
# ENV fprocess="xargs python entrypoint.py"
ENV fprocess="xargs sonic-annotator"
# Set to true to see request in function logs
ENV write_debug="false"

HEALTHCHECK --interval=5s CMD [ -e /tmp/.lock ] || exit 1
CMD [ "fwatchdog" ]
