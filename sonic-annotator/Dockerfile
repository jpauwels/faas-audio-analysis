FROM ghcr.io/openfaas/classic-watchdog:0.3.3 AS watchdog

FROM docker.io/jpauwels/sonic-annotator:v1.6-ubuntu24.04-plugins

USER root
COPY --chmod=755 --from=watchdog /fwatchdog /usr/bin/fwatchdog

COPY --chown=app:app openfaas_entrypoint.sh openfaas_entrypoint.sh
COPY --chown=app:app run-sonic-annotator.sh run-sonic-annotator.sh
COPY --chown=app:app transforms transforms
WORKDIR /tmp
USER app

# Populate example here - i.e. "cat", "sha512sum" or "node index.js"
ENV fprocess="/home/app/openfaas_entrypoint.sh"
EXPOSE 8080
HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1
CMD [ "fwatchdog" ]
