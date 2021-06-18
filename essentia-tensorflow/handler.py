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
    predictors[model_name] = ess.TensorflowPredict(graphFilename=model_path, inputs=['model/Placeholder'], outputs=['model/Sigmoid'])


def handle(audio_content):
    if os.getenv('Http_Method') == 'GET':
        return list(predictors.keys())
    elif os.getenv('Http_Method') != 'POST' or not audio_content:
        return {'error': 'Expecting audio file to be POSTed'}
    model_names = os.getenv('Http_Path', '').strip('/').split('/')
    if not model_names[0]:
        return {'error': 'Please pass one or more model names out of "{}" in the path'.format('", "'.join(predictors.keys()))}

    sample_rate = 16000
    with tempfile.NamedTemporaryFile('wb') as audio_file:
        audio_file.write(audio_content)
        loader = ess.MonoLoader(filename=audio_file.name, sampleRate=sample_rate)

    input_map = {'musicnn': [], 'vggish': []}
    for model_name in model_names:
        try:
            predictors[model_name]
        except KeyError:
            return {'error': f'Unknown model name "{model_name}"'}
        if '-vggish-' in model_name:
            input_map['vggish'].append(model_name)
        else:
            input_map['musicnn'].append(model_name)

    frame_size = {'musicnn': 512, 'vggish': 400}
    frame_hop = {'musicnn': 256, 'vggish': 160}
    input_format = {'musicnn': ess.TensorflowInputMusiCNN(), 'vggish': ess.TensorflowInputVGGish()}
    num_bands = {'musicnn': 96, 'vggish': 64}
    patch_size = {'musicnn': 187, 'vggish': 96}
    patch_hop = {'musicnn': 93, 'vggish': 93}

    pool = Pool()
    for input_type, type_models in input_map.items():
        if type_models:
            fc = ess.FrameCutter(frameSize=frame_size[input_type], hopSize=frame_hop[input_type], startFromZero=True, validFrameThresholdRatio=1)
            vtt = ess.VectorRealToTensor(shape=[1, 1, patch_size[input_type], num_bands[input_type]], patchHopSize=patch_hop[input_type], lastPatchMode='discard')
            ttp = ess.TensorToPool(namespace='model/Placeholder')
        
            loader.audio >> fc.signal
            fc.frame >> input_format[input_type].frame
            input_format[input_type].bands >> vtt.frame
            vtt.tensor >> ttp.tensor
        
            ptt = {}
            ttv = {}
            for model_name in type_models:
                ptt[model_name] = ess.PoolToTensor(namespace='model/Sigmoid')
                ttv[model_name] = ess.TensorToVectorReal()
                
                ttp.pool >> predictors[model_name].poolIn
                predictors[model_name].poolOut >> ptt[model_name].pool
                ptt[model_name].tensor >> ttv[model_name].tensor
                ttv[model_name].frame >> (pool, model_name)

            run(loader)

            for model_name in type_models:
                ttp.pool.disconnect(predictors[model_name].poolIn)
                predictors[model_name].poolOut.disconnect(ptt[model_name].pool)

    stats = PoolAggregator(defaultStats=['mean'])(pool)
    response = {model_name: stats[f'{model_name}.mean'].tolist() for model_name in model_names}
    return response
