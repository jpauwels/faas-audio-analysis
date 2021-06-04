# Mood aggressive classifiers
## Dataset
- Origin: In-house MTG collection (Laurier et al., 2009)
- Use: Classification of music by mood (aggressive/non-aggressive)
- Size: 280 full tracks + excerpts, 133/147 per class

Laurier, C., Meyers, O., Serra, J., Blech, M., & Herrera, P. (2009). Music mood annotator design and integration. In 7th International Workshop on Content-Based Multimedia Indexing (CBMI'09), pp. 156-161.

## Models
### mood_aggressive-musicnn-msd
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/dense_1/BiasAdd
- feature extractor: TensorflowInputMusiCNN
- classes: ["aggressive", "not_aggressive"]
- 5-fold acc: 0.95

### mood_aggressive-musicnn-mtt
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/dense_1/BiasAdd
- features: TensorflowInputMusiCNN
- classes: ["aggressive", "not_aggressive"]
- 5-fold acc: 0.96

### mood_aggressive-vggish-audioset
- input name: model/Placeholder
- output name: model/Sigmoid
- penultimate layer name: model/fully_connected/BiasAdd
- features: TensorflowInputVGGish
- classes: ["aggressive", "not_aggressive"]
- 5-fold acc: 0.98
