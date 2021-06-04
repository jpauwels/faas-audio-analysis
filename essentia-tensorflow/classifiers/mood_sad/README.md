# Mood sad classifiers
## Dataset
- Origin: In-house MTG collection (Laurier et al., 2009)
- Use: Classification of music by mood (sad/non-sad)
- Size: 230 full tracks + excerpts, 96/134 per class

Laurier, C., Meyers, O., Serra, J., Blech, M., & Herrera, P. (2009). Music mood annotator design and integration. In 7th International Workshop on Content-Based Multimedia Indexing (CBMI'09), pp. 156-161.

## Models
### mood_sad-musicnn-msd
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/dense_1/BiasAdd
- feature extractor: TensorflowInputMusiCNN
- classes: ["sad", "non_sad"]
- 5-fold acc: 0.86

### mood_sad-musicnn-mtt
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/dense_1/BiasAdd
- features: TensorflowInputMusiCNN
- classes: ["sad", "non_sad"]
- 5-fold acc: 0.85

### mood_sad-vggish-audioset
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/fully_connected/BiasAdd
- features: TensorflowInputVGGish
- classes: ["sad", "non_sad"]
- 5-fold acc: 0.89
