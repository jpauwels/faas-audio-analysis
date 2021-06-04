# Mood happy classifiers
## Dataset
- Origin: In-house MTG collection (Laurier et al., 2009)
- Use: Classification of music by mood (happy/non-happy)
- Size: Size: 302 full tracks + excerpts, 139/163 per class

Laurier, C., Meyers, O., Serra, J., Blech, M., & Herrera, P. (2009). Music mood annotator design and integration. In 7th International Workshop on Content-Based Multimedia Indexing (CBMI'09), pp. 156-161.

## Models
### mood_happy-musicnn-msd
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/dense_1/BiasAdd
- feature extractor: TensorflowInputMusiCNN
- classes: ["happy", "non_happy"]
- 5-fold acc: 0.81

### mood_happy-musicnn-mtt
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/dense_1/BiasAdd
- features: TensorflowInputMusiCNN
- classes: ["happy", "non_happy"]
- 5-fold acc: 0.79

### mood_happy-vggish-audioset
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/fully_connected/BiasAdd
- features: TensorflowInputVGGish
- classes: ["happy", "non_happy"]
- 5-fold acc: 0.86
