FROM jpauwels/vamp-plugins:v18.06

# 1. Use any image as your base image, or "scratch"
# 2. Add fwatchdog binary via https://github.com/openfaas/faas/releases/
# 3. Then set fprocess to the process you want to invoke per request - i.e. "cat" or "my_binary"

ADD https://github.com/openfaas/faas/releases/download/0.8.0/fwatchdog /usr/bin
RUN chmod +x /usr/bin/fwatchdog

RUN mkdir -p /home/app

#RUN apk --no-cache add curl \
#    && echo "Pulling watchdog binary from Github." \
#    && curl -sSL https://github.com/openfaas/faas/releases/download/0.8.0/fwatchdog > /usr/bin/fwatchdog \
#    && chmod +x /usr/bin/fwatchdog \
#    && cp /usr/bin/fwatchdog /home/app \
#    && apk del curl --no-cache

# Add non root user

RUN addgroup --system app && adduser --system --ingroup app app

RUN chown app /home/app

WORKDIR /home/app

USER app

COPY transforms transforms

# Populate example here - i.e. "cat", "sha512sum" or "node index.js"
ENV fprocess="xargs sonic-annotator"
# Set to true to see request in function logs
ENV write_debug="false"
ENV read_timeout="300s" write_timeout="300s"

HEALTHCHECK --interval=5s CMD [ -e /tmp/.lock ] || exit 1
CMD [ "fwatchdog" ]
