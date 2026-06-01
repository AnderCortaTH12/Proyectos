import os
import numpy as np
from skimage.io import imread
from skimage.color import rgb2gray
from skimage.transform import resize
from skimage.feature import hog
from sklearn.svm import SVC
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay
import matplotlib.pyplot as plt


# --- CONFIGURACIÓN ---
image_size = (128, 128)
orientations = 9
pixels_per_cell = (8, 8)

# --- RUTAS BASE ---
base_path = 'spiral'
clases = ['healthy', 'parkinson']

# --- FUNCIÓN DE CARGA Y PROCESAMIENTO ---
def cargar_hog_de_carpeta(carpeta_base, clases):
    X, y = [], []
    for etiqueta, clase in enumerate(clases):
        carpeta = os.path.join(carpeta_base, clase)
        for archivo in os.listdir(carpeta):
            if archivo.lower().endswith('.png'):
                ruta = os.path.join(carpeta, archivo)
                imagen = imread(ruta)

                # Si tiene canal alfa (RGBA), convertir a RGB
                if imagen.ndim == 3 and imagen.shape[2] == 4:
                    imagen = imagen[:, :, :3]

                imagen = rgb2gray(imagen)
                imagen = resize(imagen, image_size)

                # Extraer HOG
                caracteristicas = hog(imagen,
                                      orientations=orientations,
                                      pixels_per_cell=pixels_per_cell,
                                      cells_per_block=(2, 2),
                                      block_norm='L2-Hys')
                X.append(caracteristicas)
                y.append(etiqueta)
    return np.array(X), np.array(y)

# --- CARGA DE DATOS ---
X_train, y_train = cargar_hog_de_carpeta(os.path.join(base_path, 'training'), clases)
X_test, y_test = cargar_hog_de_carpeta(os.path.join(base_path, 'testing'), clases)

# --- ENTRENAMIENTO ---
modelo = SVC(kernel='linear')
modelo.fit(X_train, y_train)


# --- GUARDAR MODELO ENTRENADO ---
import joblib
joblib.dump(modelo, 'modelo_svm_hog.pkl')

# --- PREDICCIÓN Y EVALUACIÓN ---
y_pred = modelo.predict(X_test)

# Clasificación detallada
print(classification_report(y_test, y_pred, target_names=clases))

# --- MATRIZ DE CONFUSIÓN ---
cm = confusion_matrix(y_test, y_pred)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=clases)
disp.plot(cmap='Blues')
plt.title("Matriz de Confusión")
plt.show()
