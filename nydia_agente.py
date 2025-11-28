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
# 1. FUNCIÓN DE PERCEPCIÓN Y CONSOLIDACIÓN (Compatibilidad total de archivos y CHUNKING)
# ----------------------------------------------------
@st.cache_data
def consolidar_archivos(uploaded_files):
    """Procesa una lista de archivos (CSV, XLS, XLSX) y devuelve un DataFrame consolidado.
       Implementa chunking para CSV para manejar archivos grandes."""
    
    if not uploaded_files:
        return pd.DataFrame() 

    dataframes = []
    
    # Definimos un tamaño de bloque (chunk) para archivos muy grandes (ej. 100,000 filas)
    CHUNK_SIZE = 100000 
    
    for file in uploaded_files:
        try:
            file_extension = file.name.split('.')[-1].lower()
            
            if file_extension in ['xls', 'xlsx']:
                # Lectura estándar de Excel
                st.info(f"Leyendo archivo Excel: {file.name}")
                df = pd.read_excel(io.BytesIO(file.getvalue()), engine='openpyxl')
                dataframes.append(df)
            
            elif file_extension == 'csv':
                st.info(f"Leyendo archivo CSV (usando chunking): {file.name}")
                file_content = io.StringIO(file.getvalue().decode('utf-8', errors='ignore'))
                
                # Intentamos detectar el delimitador automáticamente (',' o ';')
                delimiter = ','
                # Leemos las primeras 1000 líneas para intentar inferir el delimitador
                sample_lines = file_content.read(10000) 
                file_content.seek(0) # Volver al inicio para la lectura completa
                
                if sample_lines.count(';') > sample_lines.count(','):
                    delimiter = ';'
                
                
                # --- LECTURA POR BLOQUES (Chunking) para archivos grandes ---
                chunks = pd.read_csv(
                    file_content, 
                    delimiter=delimiter, 
                    on_bad_lines='skip', 
                    encoding='utf-8', 
                    chunksize=CHUNK_SIZE # Lee 100,000 filas por vez
                )
                
                # Concatenar todos los chunks
                df_chunked = pd.concat(chunks, ignore_index=True)
                dataframes.append(df_chunked)

            
            else:
                st.warning(f"Formato de archivo no soportado: {file.name}")
            
        except Exception as e:
            st.error(f"Error al leer el archivo {file.name}: {e}")
            
    if dataframes:
        df_consolidado = pd.concat(dataframes, ignore_index=True)
        # Intentar inferir objetos para asegurar la correcta lectura de tipos
        df_consolidado = df_consolidado.infer_objects() 
        return df_consolidado
    else:
        return pd.DataFrame()

# ----------------------------------------------------
# 2. FUNCIÓN DE PROCESAMIENTO NLP (CONVERSIÓN DE TEXTO A LÓGICA DE FILTRADO)
# ----------------------------------------------------

def nlp_a_filtro(df, query):
    """Convierte una instrucción en lenguaje natural a una expresión de filtrado de Pandas."""
    
    # Se añade el DataFrame al estado de la sesión para evitar pasarlo
    if 'df_original' not in st.session_state:
        st.session_state['df_original'] = df.copy()

    # Si la consulta es vacía o solo contiene espacios en blanco, no aplicar filtro.
    if not query or query.strip() == "":
        return df

    # Normalizar la consulta a minúsculas
    query_lower = query.lower().strip()
    
    # Expresión para buscar 'mostrar todas las filas' o 'reset'
    reset_pattern = r"(mostrar|ver|todas|todo|restablecer|reset|limpiar|sin) (filas|filtros|data|datos|tabla)"
    if re.search(reset_pattern, query_lower):
        st.session_state['filtro_aplicado'] = None
        st.info("Filtro restablecido: Mostrando todas las filas originales.")
        return st.session_state['df_original']


    try:
        # 1. Identificar columnas candidatas (usando la versión original para inferencia)
        columnas_disponibles = list(df.columns)
        columna_a_filtrar = None
        
        # Buscar el nombre de la columna en la query (es sensible a mayúsculas/minúsculas)
        for col in columnas_disponibles:
            if col.lower() in query_lower:
                columna_a_filtrar = col
                break
        
        # Si no se encuentra, usar el NLP más avanzado
        if columna_a_filtrar is None:
            # Lógica más flexible: buscar palabras clave comunes y las columnas
            for col in columnas_disponibles:
                col_lower = col.lower()
                # Buscar coincidencias parciales con palabras clave
                if re.search(r'\b' + re.escape(col_lower.split(' ')[0]) + r'\b', query_lower):
                    columna_a_filtrar = col
                    break
            
            if columna_a_filtrar is None:
                 # Último recurso: intentar coincidir la columna que mejor se ajuste a la consulta.
                 # Esto es muy simple y se puede mejorar con un modelo NLP más complejo.
                 best_match_score = -1
                 for col in columnas_disponibles:
                     score = 0
                     if col.lower() in query_lower:
                         score = 100 # Coincidencia exacta
                     elif re.search(r'\b' + re.escape(col.lower().split(' ')[0]) + r'\b', query_lower):
                         score = 50 # Coincidencia por primera palabra
                     
                     if score > best_match_score:
                         best_match_score = score
                         columna_a_filtrar = col
                         
            if columna_a_filtrar is not None and best_match_score < 50:
                # Si el mejor match es débil, quizás el usuario no especificó columna
                columna_a_filtrar = None


        if columna_a_filtrar is None:
            # En muchos casos, el usuario quiere filtrar por VALOR, no por columna explícita.
            # Intentamos encontrar un valor literal en el DataFrame.
            
            # 2. Identificar el valor (valor_buscado)
            # Buscar el valor que está después de una palabra clave de filtrado
            match = re.search(r'(con|donde|sea|igual a|de|en|contenga|excluir|excepto) (.*)', query_lower)
            if match:
                valor_buscado = match.group(2).strip().replace('"', '').replace("'", '').replace('.', '') # Limpiamos comillas y puntos
                
                # Buscamos este valor en todas las columnas de tipo 'object' (texto)
                for col in df.select_dtypes(include='object').columns:
                    if df[col].astype(str).str.lower().str.contains(valor_buscado).any():
                        columna_a_filtrar = col
                        break
                        
            if columna_a_filtrar is None:
                st.warning("No se pudo identificar una columna válida o un patrón de filtrado en la consulta. Mostrando datos sin filtrar.")
                st.session_state['filtro_aplicado'] = None
                return st.session_state['df_original']

        # Ya tenemos columna_a_filtrar. Ahora generamos la expresión.
        col = columna_a_filtrar 
        expresion_filtro = None

        # 2. Generar la expresión de filtro basado en palabras clave (mayor, menor, igual, contiene, etc.)
        
        # Filtrado por RANGO o COMPARACIÓN (para columnas numéricas o de fecha)
        if df[col].dtype in ['int64', 'float64', 'datetime64[ns]']:
            
            # Buscar un número en la consulta
            numeros = re.findall(r'(\d+\.?\d*)', query)
            
            if not numeros:
                # Si no hay número, intentar buscar una fecha
                fechas = re.findall(r'(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4}|\d{4})', query)
                if fechas:
                     valor = fechas[0]
                     if 'mayor que' in query_lower or '>' in query_lower:
                         expresion_filtro = f"@{col} > '{valor}'"
                     elif 'menor que' in query_lower or '<' in query_lower:
                         expresion_filtro = f"@{col} < '{valor}'"
                     elif 'igual a' in query_lower or '=' in query_lower:
                         expresion_filtro = f"@{col} == '{valor}'"
                     else:
                         # Por defecto, igual si solo se da el valor
                         expresion_filtro = f"@{col} == '{valor}'"
                
            else: # Si se encontró un número
                valor = float(numeros[0])
                if 'mayor que' in query_lower or '>' in query_lower:
                    expresion_filtro = f"@{col} > {valor}"
                elif 'menor que' in query_lower or '<' in query_lower:
                    expresion_filtro = f"@{col} < {valor}"
                elif 'igual a' in query_lower or '=' in query_lower:
                    expresion_filtro = f"@{col} == {valor}"
                else:
                    # Por defecto, igual si solo se da el número
                    expresion_filtro = f"@{col} == {valor}"
        
        # Filtrado por TEXTO/CATEGORÍA (para columnas tipo 'object')
        else:
            # Buscar el valor que está después de una palabra clave de filtrado
            match = re.search(r'(con|donde|sea|igual a|de|en|contenga|excluir|excepto) (.*)', query_lower)
            if match:
                valor_buscado = match.group(2).strip().replace('"', '').replace("'", '').replace('.', '')

                if 'contenga' in query_lower or 'con el texto' in query_lower or 'donde esté' in query_lower:
                    # Contiene (parcial)
                    expresion_filtro = f"@{col}.astype(str).str.contains('{valor_buscado}', case=False, regex=False)"
                elif 'no contenga' in query_lower or 'excluir' in query_lower or 'excepto' in query_lower:
                    # No Contiene (parcial, usando negación)
                    expresion_filtro = f"~@{col}.astype(str).str.contains('{valor_buscado}', case=False, regex=False)"
                else:
                    # Igual a (completo)
                    expresion_filtro = f"@{col}.astype(str).str.lower() == '{valor_buscado}'"
            
            # Caso de solo un valor (ej: 'mostrar ventas de Madrid')
            elif len(query_lower.split()) <= 4:
                # Intentamos usar el último token como valor
                valor_buscado = query_lower.split()[-1]
                expresion_filtro = f"@{col}.astype(str).str.lower() == '{valor_buscado}'"
        

        if expresion_filtro:
            # Aplicar filtro
            if expresion_filtro.startswith("~") or "str.contains" in expresion_filtro:
                # Caso especial para filtros booleanos complejos (contiene, no contiene)
                df_filtrado = df[eval(expresion_filtro.replace(f"@{col}", f"df['{col}']"))]
            else:
                # Caso estándar usando query()
                # Para evitar problemas con el espacio de nombres, inyectamos la variable
                df_filtrado = df.query(expresion_filtro.replace(f"@{col}", f"`{col}`"), engine='python')


            st.session_state['filtro_aplicado'] = expresion_filtro
            st.info(f"Filtro aplicado en la columna **{col}**: `{expresion_filtro}`. Filas resultantes: {len(df_filtrado)}")
            return df_filtrado
            
        else:
            st.warning("No se pudo generar una expresión de filtro válida a partir de la consulta. Mostrando datos sin filtrar.")
            st.session_state['filtro_aplicado'] = None
            return st.session_state['df_original']

    except Exception as e:
        st.error(f"Error en el procesamiento NLP para generar el filtro: {e}")
        st.session_state['filtro_aplicado'] = None
        return st.session_state['df_original']


# ----------------------------------------------------
# 3. FUNCIÓN DE VISUALIZACIÓN (Gráficos)
# ----------------------------------------------------

def generar_visualizacion(df_original, df, tipo_grafico, eje_x, eje_y, metodo_agregacion):
    """Genera y muestra un gráfico de Plotly Express basado en los parámetros."""
    
    if df.empty:
        st.warning("El DataFrame está vacío. No se puede generar el gráfico.")
        return

    try:
        # Aseguramos que solo usamos columnas que existen
        columnas_disponibles = list(df.columns)
        
        # Lógica para Gráficos de Agregación (Barras, Líneas, Pie)
        if tipo_grafico in ['Barras', 'Línea', 'Pie']:
            if eje_x not in columnas_disponibles or eje_y not in columnas_disponibles:
                 st.error("Por favor, selecciona columnas X e Y válidas para el gráfico.")
                 return
                 
            # Agregación: Calcula el valor agregado
            # Eliminamos filas con NaN en las columnas clave para la agregación
            df_cleaned = df.dropna(subset=[eje_x, eje_y])
            
            # La columna Y debe ser numérica para la agregación, forzamos el tipo
            # Si falla la conversión, se omite el error y se usa lo que se tenga
            try:
                df_cleaned[eje_y] = pd.to_numeric(df_cleaned[eje_y], errors='coerce')
                # Tras la coerción, eliminamos los nuevos NaN si el tipo original no era adecuado
                df_cleaned = df_cleaned.dropna(subset=[eje_y])
            except:
                st.warning(f"La columna '{eje_y}' no es completamente numérica. Solo se usarán valores válidos.")
                pass

            if df_cleaned.empty:
                st.warning("No quedan datos válidos después de limpiar para la agregación.")
                return


            df_agregado = df_cleaned.groupby(eje_x)[eje_y].agg(metodo_agregacion).reset_index()
            y_col_name = f"{metodo_agregacion} de {eje_y}"
            df_agregado.rename(columns={eje_y: y_col_name}, inplace=True)
            
            if df_agregado.empty:
                st.warning("El resultado de la agregación está vacío.")
                return

            if tipo_grafico == 'Barras':
                fig = px.bar(df_agregado, x=eje_x, y=y_col_name, title=f"Distribución: {metodo_agregacion} de {eje_y} por {eje_x}")

            elif tipo_grafico == 'Línea':
                fig = px.line(df_agregado, x=eje_x, y=y_col_name, title=f"Tendencia: {metodo_agregacion} de {eje_y} a lo largo de {eje_x}")
            
            elif tipo_grafico == 'Pie':
                # El gráfico de Pie requiere una columna para los segmentos (names) y una para los valores (values)
                fig = px.pie(df_agregado, names=eje_x, values=y_col_name, 
                             title=f"Composición: {metodo_agregacion} de {eje_y} por {eje_x}")
            

        # Lógica para Gráficos Sin Agregación (Dispersión, Histograma, Caja)
        elif tipo_grafico == 'Dispersión (Scatter)':
            if eje_x not in columnas_disponibles or eje_y not in columnas_disponibles:
                 st.error("Por favor, selecciona columnas X e Y válidas para el gráfico.")
                 return
            fig = px.scatter(df, x=eje_x, y=eje_y, title=f"Relación entre {eje_x} y {eje_y}", hover_data=columnas_disponibles)
            
        elif tipo_grafico == 'Histograma':
            if eje_y not in columnas_disponibles:
                 st.error("Por favor, selecciona una columna Y válida para el gráfico.")
                 return
            fig = px.histogram(df, x=eje_y, title=f"Distribución de {eje_y}")
            
        elif tipo_grafico == 'Caja (Box Plot)':
            if eje_x not in columnas_disponibles or eje_y not in columnas_disponibles:
                 st.error("Por favor, selecciona columnas X e Y válidas para el gráfico.")
                 return
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
    
    st.title("🤖 NydIA: Agente de Análisis de Datos con NLP")
    st.markdown("Carga tus datos, describe qué necesitas y NydIA te ayudará a filtrar y visualizar.")

    # 1. CARGA DE ARCHIVOS
    uploaded_files = st.file_uploader(
        "Carga tus archivos de Excel (.xls/.xlsx) o CSV (.csv) aquí:",
        type=['csv', 'xls', 'xlsx'],
        accept_multiple_files=True
    )

    df_original = consolidar_archivos(uploaded_files)

    if df_original.empty:
        st.warning("Esperando la carga de archivos...")
        # Limpiar el estado de la sesión si no hay archivos
        st.session_state['df_original'] = pd.DataFrame()
        st.session_state['df_filtrado'] = pd.DataFrame()
        return
        
    # Inicializar estado de sesión
    if 'df_original' not in st.session_state or st.session_state['df_original'].empty:
        st.session_state['df_original'] = df_original.copy()
        st.session_state['df_filtrado'] = df_original.copy()
        st.session_state['filtro_aplicado'] = None # Nuevo estado para rastrear el filtro

    df = st.session_state['df_filtrado']
    
    # ----------------------------------------------------
    # 2. PROCESAMIENTO NLP Y FILTRADO
    # ----------------------------------------------------
    st.header("1. Filtrado de Datos (Lenguaje Natural)")
    
    col_filter, col_status = st.columns([3, 1])

    with col_filter:
        query = st.text_input(
            "¿Qué datos quieres analizar? (Ej: 'mostrar solo las filas con ventas mayores a 5000' o 'restablecer filtros')",
            key="nlp_query"
        )
    
    with col_status:
        st.markdown(f"**Filas cargadas:** {len(st.session_state['df_original']):,}")
        st.markdown(f"**Filas filtradas:** {len(df):,}")


    # Si la consulta cambia o se está procesando
    if st.session_state.get('last_query') != query:
        st.session_state['df_filtrado'] = nlp_a_filtro(st.session_state['df_original'], query)
        st.session_state['last_query'] = query
        df = st.session_state['df_filtrado'] # Actualizar df para el resto del script

    
    # ----------------------------------------------------
    # 3. VISUALIZACIÓN
    # ----------------------------------------------------
    st.header("2. Visualización y Gráficos")
    
    if df.empty:
        st.warning("No hay datos para visualizar después del filtrado.")
        return

    columnas_disponibles = list(df.columns)
    
    # Menús de selección para el gráfico
    col_tipo, col_ejes, col_agg = st.columns([1.5, 2, 1.5])
    
    with col_tipo:
        tipo_grafico = st.selectbox(
            "Tipo de Gráfico",
            ('Barras', 'Línea', 'Dispersión (Scatter)', 'Histograma', 'Caja (Box Plot)', 'Pie'),
            key="chart_type"
        )

    with col_ejes:
        # Los ejes se seleccionan del DataFrame filtrado (que es el que se va a graficar)
        eje_x = st.selectbox("Eje X (Categoría o Agrupación)", columnas_disponibles, index=0)
        eje_y = st.selectbox("Eje Y (Valor a medir/contar)", columnas_disponibles, index=1 if len(columnas_disponibles) > 1 else 0)

    with col_agg:
        # Opciones de agregación, solo necesarias para Barras, Líneas y Pie
        metodo_agregacion = st.selectbox(
            "Método de Agregación (Suma, Promedio, etc.)",
            ('sum', 'mean', 'count', 'median', 'min', 'max'),
            key="agg_method",
            disabled=(tipo_grafico not in ['Barras', 'Línea', 'Pie'])
        )

    if st.button("Generar Gráfico", type="primary"):
        generar_visualizacion(
            st.session_state['df_original'], 
            df, 
            tipo_grafico, 
            eje_x, 
            eje_y, 
            metodo_agregacion
        )
        
    # ----------------------------------------------------
    # 4. MUESTRA DE DATOS
    # ----------------------------------------------------
    st.header("3. Vista Previa de Datos Filtrados")
    st.dataframe(df.head(1000), use_container_width=True) # Mostrar solo las primeras 1000 filas para evitar sobrecarga

if __name__ == "__main__":
    main()