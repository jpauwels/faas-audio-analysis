from glob import glob
import os
import tempfile
from math import ceil
import numpy as np
import essentia.streaming as ess
from essentia import Pool, run, reset
from essentia.standard import PoolAggregator, MonoLoader, FrameGenerator
from essentia import log


log.infoActive = False
log.warningActive = False


predictors = {}
for model_path in sorted(glob('function/classifiers/*/*.pb')):
    model_name = os.path.splitext(os.path.basename(model_path))[0]
    predictors[model_name] = ess.TensorflowPredict(graphFilename=model_path, inputs=['model/Placeholder'], outputs=['model/Sigmoid'])


def handle(event, context):
    if event.method == 'GET':
        return {
            "statusCode": 200,
            "body": list(predictors.keys()),
        }
    elif event.method != 'POST' or not event.body:
        return {
            "statusCode": 400,
            "body": {'error': 'Expecting audio file to be POSTed'},
        }
    model_names = event.path.strip('/').split('/')
    if not model_names[0]:
        return {
            "statusCode": 400,
            "body": {'error': 'Please pass one or more model names out of "{}" in the path'.format('", "'.join(predictors.keys()))},
        }

    sample_rate = 16000
    with tempfile.NamedTemporaryFile('wb') as audio_file:
        audio_file.write(event.body)
        samples = MonoLoader(filename=audio_file.name, sampleRate=sample_rate)()

    input_map = {'musicnn': [], 'vggish': []}
    for model_name in model_names:
        try:
            predictors[model_name]
        except KeyError:
            return {
                "statusCode": 400,
                "body": {'error': f'Unknown model name "{model_name}"'},
            }
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
            segment_size = patch_size[input_type] * (frame_hop[input_type] - 1) + frame_size[input_type]
            segment_hop = patch_hop[input_type] * frame_hop[input_type]
            segment = np.empty(segment_size, dtype=np.single)
            input_vector = ess.VectorInput(segment)
            fc = ess.FrameCutter(frameSize=frame_size[input_type], hopSize=frame_hop[input_type], startFromZero=True, validFrameThresholdRatio=1)
            vtt = ess.VectorRealToTensor(shape=[1, 1, patch_size[input_type], num_bands[input_type]], patchHopSize=patch_hop[input_type], lastPatchMode='discard')
            ttp = ess.TensorToPool(namespace='model/Placeholder')
        
            input_vector.data >> fc.signal
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

            for s in FrameGenerator(np.hstack((np.zeros(ceil(frame_size[input_type]/2)), samples)), frameSize=segment_size, hopSize=segment_hop, startFromZero=True, validFrameThresholdRatio=1, lastFrameToEndOfFile=True):
                segment[:] = s
                reset(input_vector)
                run(input_vector)

            for model_name in type_models:
                ttp.pool.disconnect(predictors[model_name].poolIn)
                predictors[model_name].poolOut.disconnect(ptt[model_name].pool)

    stats = PoolAggregator(defaultStats=['mean'])(pool)
    response = {model_name: stats[f'{model_name}.mean'].tolist() for model_name in model_names}
    return {
        "statusCode": 200,
        "body": response,
    }
