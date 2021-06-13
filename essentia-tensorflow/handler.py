from glob import glob
import os
import tempfile
import essentia.streaming as ess
from essentia import Pool, run
from essentia.standard import PoolAggregator
from essentia import log


log.infoActive = False
log.warningActive = False


predictors = {}
for model_path in sorted(glob('function/classifiers/*/*.pb')):
    model_name = os.path.splitext(os.path.basename(model_path))[0]
    if '-vggish-' in model_name:
        predictors[model_name] = ess.TensorflowPredictVGGish(graphFilename=model_path, accumulate=False)
    else:
        predictors[model_name] = ess.TensorflowPredictMusiCNN(graphFilename=model_path, accumulate=False)


def handle(audio_content):
    if os.getenv('Http_Method') == 'GET':
        return list(predictors.keys())
    elif os.getenv('Http_Method') != 'POST' or not audio_content:
        return {'error': 'Expecting audio file to be POSTed'}
    model_names = os.getenv('Http_Path', '').strip('/').split('/')
    if not model_names[0]:
        return {'error': 'Please pass one or more model names out of "{}" in the path'.format('", "'.join(predictors.keys()))}

    with tempfile.NamedTemporaryFile('wb') as audio_file:
        audio_file.write(audio_content)
        loader = ess.MonoLoader(filename=audio_file.name, sampleRate=16000)
    pool = Pool()
    for model_name in model_names:
        try:
            loader.audio >> predictors[model_name].signal
            predictors[model_name].predictions >> (pool, model_name)
        except KeyError:
            return {'error': f'Unknown model name "{model_name}"'}
    run(loader)
    stats = PoolAggregator(defaultStats=['mean'])(pool)
    response = {model_name: stats[f'{model_name}.mean'].tolist() for model_name in model_names}
    return response
