import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

# ----------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# ----------------------------------------------------
st.set_page_config(layout="wide", page_title="NydIA: Agente Conversacional de Análisis")

# ----------------------------------------------------
# INICIALIZACIÓN DEL ESTADO DE SESIÓN (Memoria del Chat y Sugerencias)
# ----------------------------------------------------
def initialize_session_state():
    """Inicializa el estado de la sesión para el chat y las sugerencias de NydIA."""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "¡Hola! Soy NydIA. Carga tus archivos de datos para empezar. ¿Qué análisis te gustaría hacer?"}
        ]
    # Se inicializan las sugerencias para guiar los selectores
    if 'suggestion_x' not in st.session_state:
        st.session_state.suggestion_x = None
    if 'suggestion_y' not in st.session_state:
        st.session_state.suggestion_y = None
    if 'suggestion_type' not in st.session_state:
        st.session_state.suggestion_type = 'Barras'
    if 'df_loaded' not in st.session_state:
        st.session_state.df_loaded = False
    
initialize_session_state()

# ----------------------------------------------------
# 1. FUNCIÓN DE PERCEPCIÓN Y CONSOLIDACIÓN (Compatibilidad total de archivos)
# ----------------------------------------------------
@st.cache_data(show_spinner="Consolidando archivos...")
def consolidar_archivos(uploaded_files):
    """Procesa una lista de archivos (CSV, XLS, XLSX) y devuelve un DataFrame consolidado."""
    
    if not uploaded_files:
        return pd.DataFrame() 

    dataframes = []
    
    for file in uploaded_files:
        try:
            file_extension = file.name.split('.')[-1].lower()
            
            if file_extension in ['xls', 'xlsx']:
                df = pd.read_excel(io.BytesIO(file.getvalue()), engine='openpyxl')
            elif file_extension == 'csv':
                file_content = io.StringIO(file.getvalue().decode('utf-8', errors='ignore'))
                try:
                    df = pd.read_csv(file_content, delimiter=',', engine='python')
                except Exception:
                    file_content.seek(0)
                    df = pd.read_csv(file_content, delimiter=';', engine='python')

            else:
                st.warning(f"Formato no soportado para el archivo {file.name}.")
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
    Intenta interpretar la pregunta del usuario para preseleccionar el gráfico y actualiza el estado
    de la sesión con las sugerencias.
    """
    pregunta = pregunta.lower().strip()
    
    dimensiones = [col.lower() for col in df.columns]
    metricas = [col.lower() for col in df.select_dtypes(include=['number']).columns]
    
    eje_x, eje_y, tipo = None, None, 'Barras'
    
    # Detección del tipo de gráfico
    if 'linea' in pregunta or 'tendencia' in pregunta:
        tipo = 'Líneas'
    elif 'dispersión' in pregunta or 'scatter' in pregunta:
        tipo = 'Dispersión (Scatter)'
    elif 'caja' in pregunta or 'boxplot' in pregunta:
        tipo = 'Caja (Box Plot)'
    elif 'torta' in pregunta or 'pie' in pregunta or 'proporción' in pregunta or 'porcentaje' in pregunta:
        tipo = 'Torta (Pie)'
        
    # Detección de ejes (métricas)
    for m in metricas:
        if m in pregunta:
            # Encuentra el nombre original usando el índice de la columna numérica
            col_name = df.select_dtypes(include=['number']).columns.tolist()
            if m in dimensiones:
                 eje_y = df.columns.tolist()[dimensiones.index(m)]
            else:
                 # Si la palabra clave coincide con una métrica, pero no es exacta, toma la primera numérica
                 eje_y = col_name[0] if col_name else None
            break
            
    # Detección de ejes (dimensiones/categorías)
    for d in dimensiones:
        if d in pregunta and d != (eje_y.lower() if eje_y else None): 
            eje_x = df.columns.tolist()[dimensiones.index(d)]
            break

    # Valores por defecto si no se detecta nada, pero hay datos
    if not eje_y and metricas:
        eje_y = df.select_dtypes(include=['number']).columns.tolist()[0]
    if not eje_x and dimensiones:
        # Intenta seleccionar la primera columna categórica si es posible
        cat_cols = df.select_dtypes(include=['object']).columns.tolist()
        if cat_cols:
            eje_x = cat_cols[0]
        else:
             eje_x = df.columns.tolist()[0]


    # Actualizar estado de la sesión con las sugerencias
    st.session_state.suggestion_x = eje_x
    st.session_state.suggestion_y = eje_y
    st.session_state.suggestion_type = tipo
    
    
    # Generar respuesta de NydIA para el chat
    respuesta = "Interpretación: "
    if eje_y:
        respuesta += f"Métrica (Eje Y): **{eje_y}**. "
    if eje_x:
        respuesta += f"Dimensión (Eje X): **{eje_x}**. "
    respuesta += f"Tipo de Gráfico: **{tipo}**. Los valores han sido preseleccionados en la sección '3. Configuración Final'."
    
    if not eje_x and not eje_y:
         respuesta = "No pude identificar la Métrica ni la Dimensión. Por favor, sé más específico (ej: 'Quiero la suma de Venta por País en un gráfico de barras')."
         
    return respuesta

# ----------------------------------------------------
# 3. FUNCIÓN DE CHAT INTERACTIVO
# ----------------------------------------------------
def handle_chat_input(df):
    """Procesa la entrada del chat del usuario y actualiza la conversación."""
    user_prompt = st.session_state.chat_prompt
    
    if user_prompt:
        # Añadir prompt del usuario al historial
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        
        # Procesar con NLP y obtener sugerencia
        nydia_response = nydia_procesar_lenguaje_natural(df, user_prompt)
        
        # Añadir respuesta de NydIA al historial
        st.session_state.chat_history.append({"role": "assistant", "content": nydia_response})
        st.session_state.chat_prompt = "" # Limpiar el input

# ----------------------------------------------------
# 4. FUNCIÓN PRINCIPAL DE LA INTERFAZ
# ----------------------------------------------------
def interfaz_agente_analisis(df_original):
    
    st.title("🤖 NydIA: Agente Conversacional de Análisis")
    st.markdown("---")
    
    # --- PANELES LATERALES (CHAT Y FILTROS) ---
    
    # Panel 1: Chat con NydIA (parte superior de la sidebar)
    st.sidebar.header("💬 1. Chatea con NydIA")
    
    # Usar un container para el historial de chat
    chat_container = st.sidebar.container(height=300)
    
    for message in st.session_state.chat_history:
        with chat_container:
            if message["role"] == "user":
                st.chat_message("user").write(message["content"])
            else:
                st.chat_message("assistant").write(message["content"])

    # Evita errores si no hay datos cargados
    if not st.session_state.df_loaded:
        st.sidebar.caption("Carga tus datos para iniciar la conversación.")
        return 

    # Input del chat
    st.sidebar.chat_input(
        "Pregúntale a NydIA (ej: 'Ventas por Región en torta')", 
        key="chat_prompt", 
        on_submit=lambda: handle_chat_input(df_original)
    )

    st.sidebar.markdown("---")
    st.sidebar.header("🔍 2. Refinar y Filtrar")
    
    df = df_original.copy()
    
    # Detección de columnas de fecha para el filtro (Mejorado)
    datetime_cols = []
    for col in df.columns:
        # Intentar parsear si es de tipo object
        if df[col].dtype == 'object':
            try:
                # Usa errors='coerce' para convertir valores no válidos en NaT (Not a Time)
                temp_series = pd.to_datetime(df[col], errors='coerce')
                # Solo considera columna de fecha si tiene más del 50% de valores válidos
                if temp_series.notna().sum() / len(df) > 0.5:
                    df[col] = temp_series # Actualiza la columna en el df para el filtrado
                    datetime_cols.append(col)
            except Exception:
                pass 
        # Si ya es datetime
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            datetime_cols.append(col)
    
    # Filtro de Fechas
    if datetime_cols:
        col_fecha = st.sidebar.selectbox("Columna de Fecha:", ['Seleccionar'] + datetime_cols)
        
        if col_fecha != 'Seleccionar':
            # Trabajar solo con las fechas válidas de la columna seleccionada
            df_fechas_validas = df[col_fecha].dropna()
            
            if not df_fechas_validas.empty:
                # Asegurar que se trabaja con el tipo date para los selectores de fecha
                min_date = df_fechas_validas.min().date()
                max_date = df_fechas_validas.max().date()
                
                fecha_inicio = st.sidebar.date_input('Fecha de Inicio', value=min_date, min_value=min_date, max_value=max_date, key='date_start')
                fecha_fin = st.sidebar.date_input('Fecha de Fin', value=max_date, min_value=min_date, max_value=max_date, key='date_end')
                
                if fecha_inicio <= fecha_fin:
                    df = df[
                        (df[col_fecha].dt.date >= fecha_inicio) & 
                        (df[col_fecha].dt.date <= fecha_fin)
                    ]
                else:
                    st.sidebar.error("La fecha de inicio debe ser anterior o igual a la fecha de fin.")
    
    # Verificar si el DataFrame quedó vacío después de los filtros
    if df.empty:
        st.error("No hay datos para graficar después de aplicar los filtros.")
        return
        
    # Filtros de Texto (Categorías) - SOLUCIÓN A TYPEERROR EN SORTED()
    text_cols = df.select_dtypes(include=['object']).columns
    for col in text_cols:
        # Solo para columnas con una cantidad manejable de valores únicos
        if df[col].nunique() <= 50:
            
            # 🌟 Corrección: Convertir a str antes de unique() y sorted() para evitar TypeError con NaN
            unique_values = df[col].dropna().astype(str).unique().tolist()
            opciones_filtro = ['TODOS'] + sorted(unique_values)
            
            seleccion = st.sidebar.selectbox(f"Filtrar por **{col}**:", opciones_filtro, key=f"filter_{col}")
            if seleccion != 'TODOS':
                # Filtro aplicado sobre la versión string
                df = df[df[col].astype(str) == seleccion]
    
    # Filtro de Rango Numérico
    columnas_numericas_original = df_original.select_dtypes(include=['number']).columns.tolist()
    if columnas_numericas_original:
        col_num_a_filtrar = st.sidebar.selectbox("Filtro Rango en Columna:", ['Seleccionar'] + columnas_numericas_original)
        if col_num_a_filtrar != 'Seleccionar':
            min_val = float(df_original[col_num_a_filtrar].min())
            max_val = float(df_original[col_num_a_filtrar].max())
            rango_seleccionado = st.sidebar.slider(
                f"Rango de {col_num_a_filtrar}", min_value=min_val, max_value=max_val,
                value=(min_val, max_val), step=max(0.01, (max_val - min_val) / 100),
                key='numeric_range_filter'
            )
            df = df[
                (df[col_num_a_filtrar] >= rango_seleccionado[0]) & 
                (df[col_num_a_filtrar] <= rango_seleccionado[1])
            ]
    
    # Verificar nuevamente si el DataFrame quedó vacío
    if df.empty:
        st.error("No hay datos para graficar después de aplicar los filtros.")
        return

    # ------------------------------------
    # C. CONFIGURACIÓN FINAL DEL GRÁFICO (USA LAS SUGERENCIAS DEL CHAT)
    # ------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.header("📈 3. Configuración Final")
    
    columnas_disponibles = df.columns.tolist() 
    columnas_numericas_filtradas = df.select_dtypes(include=['number']).columns.tolist()

    if not columnas_numericas_filtradas:
        st.error("La selección actual no contiene columnas numéricas para la Métrica (Eje Y).")
        return

    # --- Lógica de Selección Robusta para usar sugerencias del chat ---
    sug_x = st.session_state.suggestion_x
    sug_y = st.session_state.suggestion_y
    sug_type = st.session_state.suggestion_type

    # Determinar el índice inicial basado en la sugerencia de NydIA
    eje_x_index = columnas_disponibles.index(sug_x) if sug_x in columnas_disponibles else 0
    eje_y_index = columnas_numericas_filtradas.index(sug_y) if sug_y in columnas_numericas_filtradas else 0
        
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
    tipo_grafico_index = tipos_grafico.index(sug_type) if sug_type in tipos_grafico else 0
    
    tipo_grafico = st.sidebar.selectbox(
        "Tipo de Gráfico:", 
        tipos_grafico,
        index=tipo_grafico_index
    )

    metodo_agregacion = 'Ninguna'
    if tipo_grafico in ['Barras', 'Líneas', 'Torta (Pie)']:
        metodo_agregacion = st.sidebar.selectbox(
            "Método de Agregación:", 
            ['Suma', 'Promedio', 'Conteo']
        )
    
    
    # ------------------------------------
    # D. GENERACIÓN DEL GRÁFICO (ACCIÓN)
    # ------------------------------------
    
    st.subheader(f"Resultado | Tipo: **{tipo_grafico}** | Filas analizadas: {len(df)}")

    try:
        # Validación final de columnas
        if eje_y not in df.columns or (eje_x not in df.columns and tipo_grafico != 'Histograma'):
             st.error(f"Las columnas seleccionadas ('{eje_x}' o '{eje_y}') no existen en el conjunto de datos filtrado. Revisa la sección 3.")
             return
                 
        if tipo_grafico in ['Barras', 'Líneas', 'Torta (Pie)']:
            
            # 🌟 CORRECCIÓN CRÍTICA: Manejo de valores nulos en el eje de agrupación (eje_x)
            df_group = df.copy() 
            # Rellenar NaN en la columna de agrupación para evitar el error "DataFrame agregado está vacío"
            # Los NaT (Not a Time) o NaNs se convierten a 'Sin Categoría'
            if eje_x in df_group.columns:
                 df_group[eje_x] = df_group[eje_x].fillna('Sin Categoría').astype(str)
            
            # Agregación de datos
            if metodo_agregacion == 'Suma':
                df_agregado = df_group.groupby(eje_x, dropna=False)[eje_y].sum().reset_index(name=f'Suma de {eje_y}')
            elif metodo_agregacion == 'Promedio':
                df_agregado = df_group.groupby(eje_x, dropna=False)[eje_y].mean().reset_index(name=f'Promedio de {eje_y}')
            else: # Conteo
                # Usar size() y reset_index para un conteo simple de filas por grupo
                df_agregado = df_group.groupby(eje_x, dropna=False).size().reset_index(name='Conteo de Elementos')
            
            if df_agregado.empty:
                 st.warning("El DataFrame agregado está vacío. No hay datos válidos para la Métrica/Dimensión después de los filtros.")
                 return
                 
            y_col_name = df_agregado.columns[-1] 
            
            if tipo_grafico == 'Barras':
                fig = px.bar(df_agregado, x=eje_x, y=y_col_name, title=f"Distribución: {metodo_agregacion} de {eje_y} por {eje_x}")
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
        st.error(f"Ocurrió un error al generar el gráfico. Esto puede deberse a tipos de datos incompatibles o datos insuficientes: {e}")
    
    st.markdown("---")
    st.caption(f"Filas originales consolidadas: {len(df_original)} | Filas analizadas después de filtros: {len(df)}")


# ----------------------------------------------------
# 5. EL BUCLE PRINCIPAL DEL AGENTE
# ----------------------------------------------------
def main():
    
    # Carga de archivos
    uploaded_files = st.file_uploader(
        "Carga tus archivos de Excel (.xls/.xlsx) o CSV (separado por comas/punto y coma):", 
        type=["xlsx", "xls", "csv"], 
        accept_multiple_files=True
    )
    
    datos_consolidados = consolidar_archivos(uploaded_files) 
    
    # Actualizar estado de carga
    if not datos_consolidados.empty:
        st.session_state.df_loaded = True
        interfaz_agente_analisis(datos_consolidados)
    else:
        st.session_state.df_loaded = False
        st.warning("Aún no hay datos cargados para que NydIA analice.")
        # Mostrar el chat aunque no haya datos, con el mensaje inicial
        interfaz_agente_analisis(pd.DataFrame())

if __name__ == "__main__":
    main()