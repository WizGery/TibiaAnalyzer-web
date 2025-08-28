## 📄 README.md

````markdown
# Tibia Analyzer — Web (Streamlit)

App para ejecutar Tibia Analyzer en la web con **Streamlit Community Cloud** (gratis).

## 🚀 Uso local
1. Instala Python 3.10+ y crea un entorno virtual.
2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
````

3. Ejecuta la app:

   ```bash
   streamlit run Home.py
   ```
4. Abre [http://localhost:8501](http://localhost:8501).

## 🌐 Despliegue en Streamlit Cloud

1. Sube este proyecto a un repositorio público en **GitHub**.
2. Ve a [Streamlit Cloud](https://streamlit.io/cloud) y crea una **New app**.
3. Conecta tu GitHub y selecciona el repo/branch.
4. En **Main file path** pon:

   ```
   streamlit_app.py
   ```
5. Haz Deploy (Streamlit detecta `requirements.txt`).

> La app puede “dormir” tras inactividad, pero se reanuda al visitarla.

## ⚙️ Flujo de uso

* Abre la URL de la app.
* **Sube tus archivos JSON** (puedes seleccionar varios).
* Ajusta filtros **Vocation** y **Mode**.
* Revisa el panel de **Pendientes** (metadatos faltantes).
* Consulta la tabla **Medias por Zona**.
* **Exporta CSV** con los resultados.

## 📌 Notas

* Los datos se procesan solo en la sesión, no se guardan en servidor.
* Para añadir autenticación o base de datos, se puede integrar con **Supabase** o **Neon** en otra versión.

```
```
