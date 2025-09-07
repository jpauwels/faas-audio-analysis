FROM docker.io/jpauwels/sonic-annotator:v1.7-ubuntu24.04-plugins

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends webhook jq \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /home/app
COPY --chown=app:app hooks.yaml .
COPY --chown=app:app run-sonic-annotator.sh run-sonic-annotator.sh
COPY --chown=app:app transforms transforms
USER app

ENTRYPOINT ["webhook"]
CMD ["-hooks", "hooks.yaml", "-verbose", "-port", "5000", "-http-methods", "POST", "-urlprefix", ""]
EXPOSE 5000
