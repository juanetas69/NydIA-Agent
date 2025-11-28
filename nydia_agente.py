import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

# ----------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# ----------------------------------------------------
st.set_page_config(layout="wide", page_title="NydIA: Análisis Multi-Formato con Gráfico Pie")

# ----------------------------------------------------
# 1. FUNCIÓN DE PERCEPCIÓN Y CONSOLIDACIÓN (Compatibilidad total de archivos)
# ----------------------------------------------------
@st.cache_data
def consolidar_archivos(uploaded_files):
    """Procesa una lista de archivos (CSV, XLS, XLSX) y devuelve un DataFrame consolidado."""
    
    if not uploaded_files:
        return pd.DataFrame() 

    dataframes = []
    
    for file in uploaded_files:
        try:
            file_extension = file.name.split('.')[-1].lower()
            
            if file_extension in ['xls', 'xlsx']:
                # Lectura de Excel
                df = pd.read_excel(io.BytesIO(file.getvalue()), engine='openpyxl')
            elif file_extension == 'csv':
                # Lectura de CSV: Intentamos coma (,) y luego punto y coma (;)
                file_content = io.StringIO(file.getvalue().decode('utf-8', errors='ignore'))
                
                # Intento 1: Coma como delimitador
                try:
                    df = pd.read_csv(file_content, delimiter=',', engine='python')
                except Exception:
                    file_content.seek(0) # Regresar al inicio del archivo
                    # Intento 2: Punto y coma como delimitador
                    df = pd.read_csv(file_content, delimiter=';', engine='python')

            else:
                st.warning(f"Formato no soportado para el archivo {file.name}. Solo se aceptan .xls, .xlsx, .csv.")
                continue

            dataframes.append(df)
            
        except Exception as e:
            st.error(f"Error al leer el archivo {file.name}: {e}")
            
    if dataframes:
        df_consolidado = pd.concat(dataframes, ignore_index=True)
        df_consolidado = df_consolidado.infer_objects()
        return df_consolidado
    else:
        return pd.DataFrame()

# ----------------------------------------------------
# 2. FUNCIÓN DE NLP BASADA EN REGLAS (NydIA - CEREBRO DE LENGUAJE NATURAL)
# ----------------------------------------------------
def nydia_procesar_lenguaje_natural(df, pregunta):
    """
    Intenta interpretar la pregunta del usuario para preseleccionar el gráfico.
    """
    pregunta = pregunta.lower().strip()
    
    dimensiones = [col.lower() for col in df.columns]
    metricas = [col.lower() for col in df.select_dtypes(include=['number']).columns]
    
    eje_x, eje_y, tipo = None, None, 'Barras'
    
    # Intenta determinar el tipo de gráfico (AÑADIDO: Torta)
    if 'linea' in pregunta or 'tendencia' in pregunta:
        tipo = 'Líneas'
    elif 'dispersión' in pregunta or 'scatter' in pregunta:
        tipo = 'Dispersión (Scatter)'
    elif 'caja' in pregunta or 'boxplot' in pregunta:
        tipo = 'Caja (Box Plot)'
    elif 'torta' in pregunta or 'pie' in pregunta or 'proporción' in pregunta:
        tipo = 'Torta (Pie)'
        
    # Intenta determinar los ejes X e Y por coincidencia de palabras clave
    for m in metricas:
        if m in pregunta:
            # Encuentra el nombre original de la columna
            eje_y = df.select_dtypes(include=['number']).columns.tolist()[dimensiones.index(m)]
            break
            
    for d in dimensiones:
        if d in pregunta and d != (eje_y.lower() if eje_y else None): 
            # Encuentra el nombre original de la columna
            eje_x = df.columns.tolist()[dimensiones.index(d)]
            break

    if not eje_y and metricas:
        eje_y = df.select_dtypes(include=['number']).columns.tolist()[0]
        
    st.sidebar.success(f"NydIA sugiere: Y='{eje_y or '---'}', X='{eje_x or '---'}', Tipo='{tipo}'.")
    return eje_x, eje_y, tipo


# ----------------------------------------------------
# 3. FUNCIÓN PRINCIPAL DE LA INTERFAZ
# ----------------------------------------------------
def interfaz_agente_analisis(df_original):
    
    st.title("🤖 NydIA: Agente de Análisis con Lenguaje Natural")
    st.markdown("---")
    
    if df_original.empty:
        st.warning("Carga tus archivos para empezar.")
        return

    df = df_original.copy()
    
    # ------------------------------------
    # A. INTERACCIÓN NLP Y FILTROS
    # ------------------------------------
    
    st.sidebar.header("💬 1. Pregúntale a NydIA")
    
    pregunta_nlp = st.sidebar.text_input(
        "Ej: Muestra las 'Ventas' por 'Región' en un gráfico de barras.", 
        key='nlp_input'
    )
    
    # Inicialización de variables de selección
    eje_x_auto, eje_y_auto, tipo_auto = None, None, 'Barras'
    
    if pregunta_nlp:
        eje_x_auto, eje_y_auto, tipo_auto = nydia_procesar_lenguaje_natural(df, pregunta_nlp)
        st.info(f"NydIA ha pre-seleccionado el gráfico.")

    
    # ------------------------------------
    # B. REFINAMIENTO Y FILTRADO MANUAL (BLOQUE CORREGIDO)
    # ------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 2. Refinar y Filtrar")
    
    # Filtros de Texto (Categorías) - SOLUCIÓN TYPEERROR
    text_cols = df.select_dtypes(include=['object']).columns
    for col in text_cols:
        if df[col].nunique() <= 50:
            
            # Conversión a str antes de unique() y sorted()
            unique_values = df[col].dropna().astype(str).unique().tolist()
            opciones_filtro = ['TODOS'] + sorted(unique_values)
            
            seleccion = st.sidebar.selectbox(f"Filtrar por **{col}**:", opciones_filtro, key=f"filter_{col}")
            if seleccion != 'TODOS':
                # Aplicamos el filtro comparando también el valor como str
                df = df[df[col].astype(str) == seleccion]
    
    # Filtro de Rango Numérico
    columnas_numericas = df_original.select_dtypes(include=['number']).columns.tolist()
    if columnas_numericas:
        col_num_a_filtrar = st.sidebar.selectbox("Filtro Rango en Columna:", ['Seleccionar'] + columnas_numericas)
        if col_num_a_filtrar != 'Seleccionar':
            min_val = float(df_original[col_num_a_filtrar].min())
            max_val = float(df_original[col_num_a_filtrar].max())
            rango_seleccionado = st.sidebar.slider(
                f"Rango de {col_num_a_filtrar}", min_value=min_val, max_value=max_val,
                value=(min_val, max_val), step=max(0.01, (max_val - min_val) / 100)
            )
            df = df[
                (df[col_num_a_filtrar] >= rango_seleccionado[0]) & 
                (df[col_num_a_filtrar] <= rango_seleccionado[1])
            ]
    
    if df.empty:
        st.error("No hay datos para graficar después de aplicar los filtros.")
        return

    # ------------------------------------
    # C. CONFIGURACIÓN FINAL DEL GRÁFICO
    # ------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.header("📈 3. Configuración Final")
    
    columnas_disponibles = df.columns.tolist() 
    columnas_numericas_filtradas = df.select_dtypes(include=['number']).columns.tolist()

    if not columnas_numericas_filtradas:
        st.error("La selección actual no contiene columnas numéricas para la Métrica (Eje Y).")
        return

    # Usar valores autoseleccionados por NydIA si son válidos
    eje_x_index = columnas_disponibles.index(eje_x_auto) if eje_x_auto in columnas_disponibles else 0
    eje_y_index = columnas_numericas_filtradas.index(eje_y_auto) if eje_y_auto in columnas_numericas_filtradas else 0
    
    
    eje_x = st.sidebar.selectbox(
        "Dimensión (Eje X):", 
        columnas_disponibles, 
        index=eje_x_index
    )
    eje_y = st.sidebar.selectbox(
        "Métrica (Eje Y):", 
        columnas_numericas_filtradas,
        index=eje_y_index
    )

    # TIPOS DE GRÁFICO (AÑADIDO: Torta (Pie))
    tipos_grafico = ['Barras', 'Líneas', 'Dispersión (Scatter)', 'Histograma', 'Caja (Box Plot)', 'Torta (Pie)']
    tipo_grafico_index = tipos_grafico.index(tipo_auto) if tipo_auto in tipos_grafico else 0

    tipo_grafico = st.sidebar.selectbox(
        "Tipo de Gráfico:", 
        tipos_grafico,
        index=tipo_grafico_index
    )

    metodo_agregacion = 'Ninguna'
    if tipo_grafico in ['Barras', 'Líneas', 'Torta (Pie)']: # Torta necesita agregación
        metodo_agregacion = st.sidebar.selectbox(
            "Método de Agregación:", 
            ['Suma', 'Promedio', 'Conteo']
        )
    
    
    # ------------------------------------
    # D. GENERACIÓN DEL GRÁFICO (ACCIÓN)
    # ------------------------------------
    
    st.subheader(f"Resultado | Tipo: **{tipo_grafico}** | Filas analizadas: {len(df)}")

    try:
        if tipo_grafico in ['Barras', 'Líneas', 'Torta (Pie)']:
            # Agregación de datos
            if metodo_agregacion == 'Suma':
                df_agregado = df.groupby(eje_x)[eje_y].sum().reset_index(name=f'Suma de {eje_y}')
            elif metodo_agregacion == 'Promedio':
                df_agregado = df.groupby(eje_x)[eje_y].mean().reset_index(name=f'Promedio de {eje_y}')
            else: # Conteo
                df_agregado = df.groupby(eje_x).size().reset_index(name='Conteo de Elementos')
            
            y_col_name = df_agregado.columns[-1] 
            
            if tipo_grafico == 'Barras':
                fig = px.bar(df_agregado, x=eje_x, y=y_col_name, title=f"{metodo_agregacion} de {eje_y} por {eje_x}")
            elif tipo_grafico == 'Líneas':
                fig = px.line(df_agregado, x=eje_x, y=y_col_name, title=f"Tendencia: {metodo_agregacion} de {eje_y} a lo largo de {eje_x}")
            elif tipo_grafico == 'Torta (Pie)':
                # Grafico de Torta (Pie Chart)
                fig = px.pie(df_agregado, names=eje_x, values=y_col_name, title=f"Proporción de {metodo_agregacion} de {eje_y} por {eje_x}")

        elif tipo_grafico == 'Dispersión (Scatter)':
            fig = px.scatter(df, x=eje_x, y=eje_y, title=f"Relación entre {eje_x} y {eje_y}", hover_data=columnas_disponibles)
            
        elif tipo_grafico == 'Histograma':
            fig = px.histogram(df, x=eje_y, title=f"Distribución de {eje_y}")
            
        elif tipo_grafico == 'Caja (Box Plot)':
            fig = px.box(df, x=eje_x, y=eje_y, title=f"Distribución de {eje_y} por {eje_x}")
            
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Ocurrió un error al generar el gráfico. Asegúrate de que las columnas sean adecuadas para el tipo de gráfico: {e}")
    
    st.markdown("---")
    st.caption(f"Filas originales consolidadas: {len(df_original)} | Filas analizadas después de filtros: {len(df)}")


# ----------------------------------------------------
# 4. EL BUCLE PRINCIPAL DEL AGENTE
# ----------------------------------------------------
def main():
    
    uploaded_files = st.file_uploader(
        "Carga tus archivos de Excel (.xls/.xlsx) o CSV (separado por comas/punto y coma):", 
        type=["xlsx", "xls", "csv"], 
        accept_multiple_files=True
    )
    
    # La función de consolidación ahora maneja múltiples formatos
    datos_consolidados = consolidar_archivos(uploaded_files) 
    
    interfaz_agente_analisis(datos_consolidados)

if __name__ == "__main__":
    main()