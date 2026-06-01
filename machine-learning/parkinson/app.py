import streamlit as st
import numpy as np
import joblib
from skimage.io import imread
from skimage.color import rgb2gray
from skimage.transform import resize
from skimage.feature import hog
from PIL import Image

# --- CARGAR MODELO ---
modelo = joblib.load('modelo_svm_hog.pkl')
image_size = (128, 128)
orientations = 9
pixels_per_cell = (8, 8)
clases = ['Healthy', 'Parkinson']

# --- INTERFAZ ---
st.title("Detector de Parkinson en Espirales")
st.write("Subí una imagen de espiral para clasificarla.")

imagen_subida = st.file_uploader("Seleccionar imagen (.png)", type=["png", "jpg", "jpeg"])

if imagen_subida is not None:
    st.image(imagen_subida, caption='Imagen cargada', use_column_width=True)

    # --- PROCESAR LA IMAGEN ---
    imagen = Image.open(imagen_subida).convert("RGB")
    imagen = imagen.resize(image_size)
    imagen_np = np.array(imagen)
    imagen_gray = rgb2gray(imagen_np)

    caracteristicas = hog(imagen_gray,
                          orientations=orientations,
                          pixels_per_cell=pixels_per_cell,
                          cells_per_block=(2, 2),
                          block_norm='L2-Hys')
    
    # --- PREDICCIÓN ---
    prediccion = modelo.predict([caracteristicas])[0]
    clase = clases[prediccion]

    st.markdown(f"### Resultado: **{clase}**")
