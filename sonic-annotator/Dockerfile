FROM ghcr.io/openfaas/classic-watchdog:0.2.3 as watchdog

FROM docker.io/jpauwels/vamp-plugins:v18.06

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog

# Add non root user
RUN addgroup --system app && adduser app --system --ingroup app
WORKDIR /home/app
USER app

COPY openfaas_entrypoint.sh openfaas_entrypoint.sh
COPY run-sonic-annotator.sh run-sonic-annotator.sh
COPY transforms transforms
WORKDIR /tmp

# Populate example here - i.e. "cat", "sha512sum" or "node index.js"
ENV fprocess="/home/app/openfaas_entrypoint.sh"
EXPOSE 8080
HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1
CMD [ "fwatchdog" ]
