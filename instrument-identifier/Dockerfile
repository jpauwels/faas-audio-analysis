FROM busybox:1 AS downloader

ADD https://github.com/adnanh/webhook/releases/download/2.8.2/webhook-linux-amd64.tar.gz .
RUN tar xzvf webhook-linux-amd64.tar.gz


FROM docker.io/jpauwels/vampy-instrument-identification

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends jq \
 && rm -rf /var/lib/apt/lists/*
COPY --from=downloader /webhook-linux-amd64/webhook /usr/local/bin

WORKDIR /home/app
COPY --chown=app:app hooks.yaml .
COPY --chown=app:app run-sonic-annotator.sh run-sonic-annotator.sh
USER app

ENTRYPOINT ["webhook"]
CMD ["-hooks", "hooks.yaml", "-verbose", "-port", "5000", "-http-methods", "POST", "-urlprefix", ""]
EXPOSE 5000
