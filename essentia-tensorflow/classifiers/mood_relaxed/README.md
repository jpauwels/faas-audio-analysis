# Mood relaxed classifiers
## Dataset
- Origin: In-house MTG collection (Laurier et al., 2009)
- Use: Classification of music by mood (relaxed/non-relaxed)
- Size: 446 full tracks + excerpts, 145/301 per class

Laurier, C., Meyers, O., Serra, J., Blech, M., & Herrera, P. (2009). Music mood annotator design and integration. In 7th International Workshop on Content-Based Multimedia Indexing (CBMI'09), pp. 156-161.

## Models
### mood_relaxed-musicnn-msd
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/dense_1/BiasAdd
- feature extractor: TensorflowInputMusiCNN
- classes: ["relaxed", "non_relaxed"]
- 5-fold acc: 0.90

### mood_relaxed-musicnn-mtt
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/dense_1/BiasAdd
- features: TensorflowInputMusiCNN
- classes: ["relaxed", "non_relaxed"]
- 5-fold acc: 0.88

### mood_relaxed-vggish-audioset
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/fully_connected/BiasAdd
- features: TensorflowInputVGGish
- classes: ["relaxed", "non_relaxed"]
- 5-fold acc: 0.89
