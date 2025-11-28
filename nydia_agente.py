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
# INICIALIZACIÓN DE LA SESIÓN DE CHAT
# ----------------------------------------------------
def initialize_session_state():
    """Inicializa el estado de la sesión para el chat y las sugerencias de NydIA."""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "¡Hola! Soy NydIA. Carga tus archivos de datos para empezar. ¿Qué análisis te gustaría hacer?"}
        ]
    # Se inicializan las sugerencias con None o un valor seguro
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
    Intenta interpretar la pregunta del usuario para preseleccionar el gráfico y actualiza el estado.
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
            eje_y = df.select_dtypes(include=['number']).columns.tolist()[dimensiones.index(m)]
            break
            
    # Detección de ejes (dimensiones)
    for d in dimensiones:
        if d in pregunta and d != (eje_y.lower() if eje_y else None): 
            eje_x = df.columns.tolist()[dimensiones.index(d)]
            break

    # Valores por defecto si no se detecta nada, pero hay datos
    if not eje_y and metricas:
        eje_y = df.select_dtypes(include=['number']).columns.tolist()[0]
    if not eje_x and dimensiones:
        eje_x = df.columns.tolist()[0]


    # Actualizar estado de la sesión con las sugerencias
    st.session_state.suggestion_x = eje_x
    st.session_state.suggestion_y = eje_y
    st.session_state.suggestion_type = tipo
    
    
    # Generar respuesta de NydIA
    respuesta = "Interpretación: "
    if eje_y:
        respuesta += f"Métrica (Eje Y): **{eje_y}**. "
    if eje_x:
        respuesta += f"Dimensión (Eje X): **{eje_x}**. "
    respuesta += f"Tipo de Gráfico: **{tipo}**. Por favor, revisa la sección '3. Configuración Final' para confirmar."
    
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
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
        
        # Procesar con NLP y obtener sugerencia
        nydia_response = nydia_procesar_lenguaje_natural(df, user_prompt)
        
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
    
    # Detección de columnas de fecha para el filtro
    datetime_cols = []
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                if df[col].notna().sum() / len(df) > 0.5:
                    datetime_cols.append(col)
            except Exception:
                pass 
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            datetime_cols.append(col)
    
    # Filtro de Fechas
    if datetime_cols:
        col_fecha = st.sidebar.selectbox("Columna de Fecha:", ['Seleccionar'] + datetime_cols)
        
        if col_fecha != 'Seleccionar':
            df_fechas_validas = df[col_fecha].dropna()
            if not df_fechas_validas.empty:
                min_date = df_fechas_validas.min().date()
                max_date = df_fechas_validas.max().date()
                
                fecha_inicio = st.sidebar.date_input('Fecha de Inicio', value=min_date, min_value=min_date, max_value=max_date)
                fecha_fin = st.sidebar.date_input('Fecha de Fin', value=max_date, min_value=min_date, max_value=max_date)
                
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
        
    # Filtros de Texto (Categorías)
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
    
    # Verificar nuevamente si el DataFrame quedó vacío después de más filtros
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
    
    # 1. Determinar el eje X
    sug_x = st.session_state.suggestion_x
    if sug_x not in columnas_disponibles:
        # Si la sugerencia no existe en el DF filtrado, usar la primera disponible
        sug_x = columnas_disponibles[0] if columnas_disponibles else None
    
    # 2. Determinar el eje Y
    sug_y = st.session_state.suggestion_y
    if sug_y not in columnas_numericas_filtradas:
        # Si la sugerencia no existe en el DF filtrado, usar la primera numérica disponible
        sug_y = columnas_numericas_filtradas[0] if columnas_numericas_filtradas else None
        
    sug_type = st.session_state.suggestion_type

    if not sug_x or not sug_y:
        st.error("No se pueden seleccionar ejes X/Y válidos. Revisa tus filtros.")
        return
        
    eje_x = st.sidebar.selectbox(
        "Dimensión (Eje X):", 
        columnas_disponibles, 
        index=columnas_disponibles.index(sug_x)
    )
    eje_y = st.sidebar.selectbox(
        "Métrica (Eje Y):", 
        columnas_numericas_filtradas,
        index=columnas_numericas_filtradas.index(sug_y)
    )

    tipos_grafico = ['Barras', 'Líneas', 'Dispersión (Scatter)', 'Histograma', 'Caja (Box Plot)', 'Torta (Pie)']
    tipo_grafico = st.sidebar.selectbox(
        "Tipo de Gráfico:", 
        tipos_grafico,
        index=tipos_grafico.index(sug_type)
    )

    metodo_agregacion = 'Ninguna'
    if tipo_grafico in ['Barras', 'Líneas', 'Torta (Pie)']:
        metodo_agregacion = st.sidebar.selectbox(
            "Método de Agregación:", 
            ['Suma', 'Promedio', 'Conteo']
        )
    
    
    # ------------------------------------
    # D. GENERACIÓN DEL GRÁFICO
    # ------------------------------------
    
    st.subheader(f"Resultado | Tipo: **{tipo_grafico}** | Filas analizadas: {len(df)}")

    try:
        if tipo_grafico in ['Barras', 'Líneas', 'Torta (Pie)']:
            # Agregación de datos
            if metodo_agregacion == 'Suma':
                # **Aquí estaba el error potencial: si eje_y no existía en el DF filtrado, fallaba.**
                # La lógica de selección de sug_y debería haberlo prevenido, pero añadimos el chequeo.
                if eje_y not in df.columns:
                     st.error(f"La columna métrica '{eje_y}' no existe en el conjunto de datos filtrado. Selecciona otra.")
                     return
                     
                df_agregado = df.groupby(eje_x)[eje_y].sum().reset_index(name=f'Suma de {eje_y}')
            elif metodo_agregacion == 'Promedio':
                df_agregado = df.groupby(eje_x)[eje_y].mean().reset_index(name=f'Promedio de {eje_y}')
            else: # Conteo
                df_agregado = df.groupby(eje_x).size().reset_index(name='Conteo de Elementos')
            
            y_col_name = df_agregado.columns[-1] 
            
            if tipo_grafico == 'Barras':
                fig = px.bar(df_agregado, x=eje_x, y=y_col_name, title=f"{metodo_agregacion} de {eje_y} por {eje_x}")
            elif tipo_grafico == 'Líneas':
                fig = px.line(df_agregado, x=eje_x, y=y_col_name, title=f"Tendencia: {metodo_agregacion} de {eje_y} a lo