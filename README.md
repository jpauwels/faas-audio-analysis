# Audio-Analysis-as-a-Service

## Deploying the default setup
The default setup uses the configuration in `analysis/config_multicollections.py` and requires an S3-compatible object store for caching audio files. Container images for this setup are publicly available on [Docker Hub](https://hub.docker.com/u/jpauwels), therefore no build step will be necessary.

1. `cp set-secrets-sample.sh set-secrets.sh`
2. edit `set-secrets.sh` and fill in all sensitive data
3. execute `./set-secrets.sh`
4. adapt `stack.yaml` to your own orchestrator. This could involve editing any of the following keys:
   - `provider:gateway`
   - `functions:analysis:environment:CHORD_API`
   - `functions:analysis:environment:ESSENTIA_API`
   - `functions:analysis:environment:ESSENTIA_TF_MODELS_API`
   - `functions:analysis:environment:INSTRUMENTS_API`
   - `functions:analysis:environment:SONIC_ANNOTATOR_API`
   - `functions:analysis:environment:OBJECT_STORE_HOSTNAME`
   - `functions:search:environment:ANALYSIS_API`
5. `faas deploy`

## Deploying a custom setup
If you want to deploy another configuration, potentially without audio-caching object store to simplify the setup, you will need to rebuild at least the `analysis` container image before deploying. In addition to steps 1-4 from above, do:

5. change `functions:analysis:image` in `stack.yml` to a container repository you have write access to and do the same for any other functions changed
6. `faas up --skip-deploy --filter analysis` and likewise for other edited functions
7. `faas deploy`
