from glob import glob
import os
import tempfile
import essentia.standard as es
from essentia import log


log.infoActive = False
log.warningActive = False


predictors = {}
for model_path in sorted(glob('function/classifiers/*/*.pb')):
    model_name = os.path.splitext(os.path.basename(model_path))[0]
    if '-vggish-' in model_name:
        predictors[model_name] = es.TensorflowPredictVGGish(graphFilename=model_path, accumulate=True)
    else:
        predictors[model_name] = es.TensorflowPredictMusiCNN(graphFilename=model_path, accumulate=True)


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
        samples = es.MonoLoader(filename=audio_file.name, sampleRate=16000)()
    response = {}
    for model_name in model_names:
        try:
            response[model_name] = predictors[model_name](samples).mean(axis=0).tolist()
        except KeyError:
            return {'error': f'Unknown model name "{model_name}"'}
    return response
