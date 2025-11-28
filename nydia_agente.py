import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

# ----------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# ----------------------------------------------------
st.set_page_config(layout="wide", page_title="NydIA: Análisis Multi-Formato con Fechas")

# ----------------------------------------------------
# 1. FUNCIÓN DE PERCEPCIÓN Y CONSOLIDACIÓN (Ahora lee CSV, XLS, XLSX)
# ----------------------------------------------------
@st.cache_data
def consolidar_archivos(uploaded_files):
    """Procesa una lista de archivos (Excel o CSV) y devuelve un DataFrame consolidado."""
    
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
                # Lectura de CSV (asumiendo delimitador coma por defecto)
                # Usamos encoding 'latin-1' o 'cp1252' común en archivos de Excel exportados
                df = pd.read_csv(io.StringIO(file.getvalue().decode('utf-8', errors='ignore')), 
                                 delimiter=',', 
                                 engine='python') 
                # Intentamos la coma, si falla, podemos intentar el punto y coma (común en Europa)
                if len(df.columns) <= 1 and 'sep' not in df.columns:
                     df = pd.read_csv(io.StringIO(file.getvalue().decode('utf-8', errors='ignore')), 
                                      delimiter=';', 
                                      engine='python')
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
# 2. FUNCIÓN DE NLP BASADA EN REGLAS
# ----------------------------------------------------
def nydia_procesar_lenguaje_natural(df, pregunta):
    """
    Intenta interpretar la pregunta del usuario para preseleccionar el gráfico.
    """
    pregunta = pregunta.lower().strip()
    
    dimensiones = [col.lower() for col in df.columns]
    metricas = [col.lower() for col in df.select_dtypes(include=['number']).columns]
    
    eje_x, eje_y, tipo = None, None, 'Barras'
    
    # Intenta determinar el tipo de gráfico (Añadido 'Torta')
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
            eje_y = df.select_dtypes(include=['number']).columns.tolist()[dimensiones.index(m)]
            break
            
    for d in dimensiones:
        if d in pregunta and d != (eje_y.lower() if eje_y else None): 
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
    
    st.title("🤖 NydIA: Agente de Análisis Multi-Formato")
    st.markdown("---")
    
    if df_original.empty:
        st.warning("Carga tus archivos para empezar.")
        return

    df = df_original.copy()
    
    # Intentar convertir columnas de tipo 'object' a datetime si es posible
    datetime_cols = []
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                # Si la mayoría de los valores no son NaT, la consideramos una columna de fecha
                if df[col].notna().sum() / len(df) > 0.5:
                    datetime_cols.append(col)
            except Exception:
                pass 
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            datetime_cols.append(col)


    # ------------------------------------
    # A. INTERACCIÓN NLP Y FILTROS
    # ------------------------------------
    
    st.sidebar.header("💬 1. Pregúntale a NydIA")
    pregunta_nlp = st.sidebar.text_input(
        "Ej: Muestra las 'Ventas' por 'Región' en un gráfico de barras.", 
        key='nlp_input'
    )
    eje_x_auto, eje_y_auto, tipo_auto = None, None, 'Barras'
    
    if pregunta_nlp:
        eje_x_auto, eje_y_auto, tipo_auto = nydia_procesar_lenguaje_natural(df, pregunta_nlp)
        st.info(f"NydIA ha pre-seleccionado el gráfico.")

    
    # ------------------------------------
    # B. NUEVO: FILTRO DE FECHAS
    # ------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.header("🗓️ Filtro de Fechas")
    
    if datetime_cols:
        col_fecha = st.sidebar.selectbox("Columna de Fecha:", ['Seleccionar'] + datetime_cols)
        
        if col_fecha != 'Seleccionar':
            min_date = df[col_fecha].min().date()
            max_date = df[col_fecha].max().date()
            
            # Usar st.date_input para seleccionar el rango de fechas
            fecha_inicio = st.sidebar.date_input('Fecha de Inicio', value=min_date, min_value=min_date, max_value=max_date)
            fecha_fin = st.sidebar.date_input('Fecha de Fin', value=max_date, min_value=min_date, max_value=max_date)
            
            # Aplicar filtro si el rango es válido
            if fecha_inicio <= fecha_fin:
                df = df[
                    (df[col_fecha].dt.date >= fecha_inicio) & 
                    (df[col_fecha].dt.date <= fecha_fin)
                ]
            else:
                st.sidebar.error("La fecha de inicio debe ser anterior o igual a la fecha de fin.")
                
    # ------------------------------------
    # C. REFINAMIENTO Y FILTRADO MANUAL (Resto de filtros y rangos)
    # ------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.header("🔍 2. Refinar y Filtrar")
    
    # Filtros de Texto (Categorías) - CORREGIDO EL TYPEERROR
    text_cols = df.select_dtypes(include=['object']).columns
    for col in text_cols:
        if df[col].nunique() <= 50:
            unique_values = df[col].dropna().astype(str).unique().tolist()
            opciones_filtro = ['TODOS'] + sorted(unique_values)
            
            seleccion = st.sidebar.selectbox(f"Filtrar por **{col}**:", opciones_filtro, key=f"filter_{col}")
            if seleccion != 'TODOS':
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
    # D. CONFIGURACIÓN FINAL DEL GRÁFICO
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
    # E. GENERACIÓN DEL GRÁFICO (ACCIÓN)
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
    
    datos_consolidados = consolidar_archivos(uploaded_files)
    
    interfaz_agente_analisis(datos_consolidados)

if __name__ == "__main__":
    main()