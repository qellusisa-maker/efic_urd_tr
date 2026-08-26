import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px

st.set_page_config(page_title="Control de Eficiencia", layout="wide")
st.title("📊 Eficiencia - Urdimbre - Trama", text_alignment="right")

# 1. CONFIGURACIÓN: Ajusta los nombres exactos de tus columnas de Excel
DROPBOX_URL = "https://www.dropbox.com/scl/fi/gvgxz16xlx8mrwz1py21b/Metros-Telares-SDE.xlsx?rlkey=axhjepjgkakfbpn1o9u5sghti&dl=1" 
NOMBRE_HOJA = "Pasadas - metros - rendimiento"                         

COL_FECHA = "Fecha"          
COL_TELAR = "Telar"          
COL_EFICIENCIA = "Eficiencia"
COL_TURNO = "Turno"          
COL_METROS = "Metros por paño"
COL_PASADAS_ART = "Pasadas Artx100"
COL_URD = "Urd."
COL_TRAMA = "Trama"

COLUMNAS_A_USAR = [
    COL_FECHA, COL_TELAR, COL_EFICIENCIA, COL_TURNO, 
    COL_METROS, COL_PASADAS_ART, COL_URD, COL_TRAMA
]

# 2. Función de carga con limpiezas y cálculos avanzados
@st.cache_data
def cargar_y_limpiar_base_datos(url, hoja, columnas, col_eficiencia, col_fecha, col_telar, col_turno, col_metros, col_pasadas_art, col_urd, col_trama):
    try:
        respuesta = requests.get(url)
        respuesta.raise_for_status() 
        
        df = pd.read_excel(
            BytesIO(respuesta.content), 
            sheet_name=hoja, 
            usecols=columnas
        )
        
        df = df.dropna(subset=[col_telar, col_eficiencia, col_fecha, col_turno])
        
        # Normalizar ID de Telar
        df[col_telar] = pd.to_numeric(df[col_telar], errors='coerce').fillna(0).astype(int).astype(str)
        df[col_telar] = df[col_telar].str.strip()
        df = df[~df[col_telar].isin(["0", "", " ", "NAN", "NONE", "NaN", "null", "NULL"])]
        
        # Limpiar Eficiencia
        df[col_eficiencia] = df[col_eficiencia].astype(str).str.replace('%', '', regex=False).str.strip()
        df[col_eficiencia] = pd.to_numeric(df[col_eficiencia], errors='coerce')
        df = df.dropna(subset=[col_eficiencia])
        
        # Filtrar fechas y turnos
        df[col_turno] = df[col_turno].astype(str).str.strip().str.upper()
        df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
        df = df.dropna(subset=[col_fecha])
        
        # Entradas numéricas
        df[col_metros] = pd.to_numeric(df[col_metros], errors='coerce').fillna(0)
        df[col_pasadas_art] = pd.to_numeric(df[col_pasadas_art], errors='coerce').fillna(0)
        df[col_urd] = pd.to_numeric(df[col_urd], errors='coerce').fillna(0)
        df[col_trama] = pd.to_numeric(df[col_trama], errors='coerce').fillna(0)
        
        # Ecuaciones textiles
        df['Pasadas'] = df[col_metros] * df[col_pasadas_art]
        df['U/CMPX'] = df.apply(lambda r: (100000 * r[col_urd]) / r['Pasadas'] if r['Pasadas'] > 0 else 0, axis=1)
        df['T/CMPX'] = df.apply(lambda r: (100000 * r[col_trama]) / r['Pasadas'] if r['Pasadas'] > 0 else 0, axis=1)
        
        
        # Mapeo de turnos para ordenación compuesta estricta
        mapa_turnos = {"M": 1, "T": 2, "N": 3}
        df['Turno_Peso'] = df[col_turno].map(mapa_turnos).fillna(4)
        df = df.sort_values(by=[col_fecha, 'Turno_Peso']).reset_index(drop=True)
        return df
        
    except Exception as e:
        st.error(f"❌ Error crítico al procesar la base de datos: {e}")
        return None

# Cargar base completa
df_crudo = cargar_y_limpiar_base_datos(
    DROPBOX_URL, NOMBRE_HOJA, COLUMNAS_A_USAR, 
    COL_EFICIENCIA, COL_FECHA, COL_TELAR, COL_TURNO,
    COL_METROS, COL_PASADAS_ART, COL_URD, COL_TRAMA
)

if df_crudo is not None and not df_crudo.empty:
    
    df_filtrado_activo = df_crudo[df_crudo[COL_EFICIENCIA] > 0.01].reset_index(drop=True)
    
    # Restringir la visualización a las últimas 42 filas procesadas
    df_base = df_filtrado_activo.tail(500).reset_index(drop=True)
    
    # Generar lista única de turnos reales
    df_base['Fecha_Str'] = df_base[COL_FECHA].dt.strftime('%Y-%m-%d')
    lista_turnos = df_base.groupby(['Fecha_Str', COL_TURNO], as_index=False).size()
    
    mapa_turnos = {"M": 1, "T": 2, "N": 3}
    lista_turnos['Turno_Peso'] = lista_turnos[COL_TURNO].map(mapa_turnos).fillna(4)
    lista_turnos = lista_turnos.sort_values(by=['Fecha_Str', 'Turno_Peso']).reset_index(drop=True)
    
    total_turnos_disponibles = len(lista_turnos)

    # 3. CONTROLADOR EN PANTALLA PRINCIPAL
    st.write("### Navegación por Turnos:")
    
    idx_turno = st.number_input(
        label=f"Usa los botones (+) y (-) para avanzar o retroceder. Disponibles: {total_turnos_disponibles} bloques de turnos.",
        min_value=0,
        max_value=total_turnos_disponibles - 1,
        value=total_turnos_disponibles - 1,
        step=1
    )
    
    turno_seleccionado_row = lista_turnos.iloc[idx_turno]
    fecha_actual_str = turno_seleccionado_row['Fecha_Str']
    turno_actual_str = turno_seleccionado_row[COL_TURNO]
    
    fecha_dt = pd.to_datetime(fecha_actual_str)
    fecha_pantalla_str = fecha_dt.strftime('%d/%m/%Y')
    
    nombres_turnos = {"M": "Mañana", "T": "Tarde", "N": "Noche"}
    turno_usuario = nombres_turnos.get(turno_actual_str, turno_actual_str)
    
    # 4 Extracción de todos los telares activos en esa fecha y turno
    df_turno_completo = df_base[
        (df_base['Fecha_Str'] == fecha_actual_str) & 
        (df_base[COL_TURNO] == turno_actual_str)
    ].reset_index(drop=True)

    #agrupacion de variables técnicas por máquina para tener el dato neto real
    df_global_turno = df_turno_completo.groupby(COL_TELAR, as_index=False)[
        [COL_EFICIENCIA, 'U/CMPX', 'T/CMPX']
    ].mean()
    df_global_turno = df_global_turno[df_global_turno[COL_EFICIENCIA] > 0.01]

    # Calcular las métricas promedio generales de la planta para el turno actual
    if not df_global_turno.empty:
        eficiencia_promedio_turno = df_global_turno[COL_EFICIENCIA].mean()
        eficiencia_promedio_texto = f"{eficiencia_promedio_turno:.1f}%"
        
        urd_promedio_turno = df_global_turno['U/CMPX'].mean()
        urd_promedio_texto = f"{urd_promedio_turno:.2f}"
        
        trama_promedio_turno = df_global_turno['T/CMPX'].mean()
        trama_promedio_texto = f"{trama_promedio_turno:.2f}"
    else:
        eficiencia_promedio_texto = "0.0%"
        urd_promedio_texto = "0"
        trama_promedio_texto = "0"

    # Despliegue de información del turno (6 columnas alineadas)
    st.caption(f"Visualizando bloque de turno {idx_turno + 1} de {total_turnos_disponibles}")
    
    m1, m2, m3, m4, m5, m6 = st.columns(6) # <- Ampliado a 6 columnas horizontales
    m1.metric("Fecha en Pantalla", fecha_pantalla_str)
    m2.metric("Turno Activo", turno_usuario)
    m3.metric("Telares Operando", len(df_global_turno))
    m4.metric("Eficiencia Promedio", eficiencia_promedio_texto)
    m5.metric("U/CMPX Promedio", urd_promedio_texto)     # <- Nueva tarjeta de Urdido
    m6.metric("T/CMPX Promedio", trama_promedio_texto)  # <- Nueva tarjeta de Trama
    
    st.markdown("---")





    # 5. GRÁFICOS EN PARALELO DEL TURNO ACTUAL
    if not df_turno_completo.empty:
        df_global_turno = df_global_turno.sort_values(by=COL_TELAR, key=lambda x: pd.to_numeric(x, errors='coerce'))
        df_tecnico_turno = df_turno_completo.groupby(COL_TELAR, as_index=False)[['U/CMPX', 'T/CMPX']].mean()
        df_tecnico_turno = df_tecnico_turno.sort_values(by=COL_TELAR, key=lambda x: pd.to_numeric(x, errors='coerce'))

        col_izq, col_der = st.columns(2)

        with col_izq:
            fig_global = px.bar(
                df_global_turno,
                x=COL_TELAR,
                y=COL_EFICIENCIA,
                title="EFICIENCIA POR TURNO",
                labels={COL_TELAR: "Telar", COL_EFICIENCIA: "Eficiencia (%)"},
                text_auto='.1f',
                range_y=[0,100],
                color_discrete_sequence=["#1E3A8A"] 
            )
            fig_global.update_layout(xaxis_tickangle=-45, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_global, use_container_width=True)

        with col_der:
            fig_tecnico = px.bar(
                df_tecnico_turno,
                x=COL_TELAR,
                y=['U/CMPX', 'T/CMPX'], 
                barmode='group',        
                title="U/CMPX, T/CMPX POR TURNO",
                labels={COL_TELAR: "Telar", "value": "Valor Coeficiente", "variable": "Parámetro"},
                text_auto='.0f',        
                color_discrete_sequence=["#059669", "#D97706"] 
            )
            fig_tecnico.update_layout(xaxis_tickangle=-45, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_tecnico, use_container_width=True)
    else:
        st.warning(f"No hay registros de eficiencia activos para el {turno_usuario} del día {fecha_pantalla_str}.")
        
    st.markdown("---")
    
        # -----------------------------------------------------------------
    # 📈 NUEVA SECCIÓN: ANÁLISIS DE TENDENCIA INDIVIDUAL (U/CMPX y T/CMPX)
    # -----------------------------------------------------------------
    st.write("### 📈 U/CMPX  T/CMPX")
    
    # Selector exclusivo para elegir qué telar queremos estudiar a lo largo del tiempo
    lista_telares_historial = sorted(df_base[COL_TELAR].unique(), key=lambda x: int(x) if x.isdigit() else x)
    telar_hist_sel = st.selectbox("Selecciona un telar para ver su evolución temporal:", options=lista_telares_historial)
    
    # Filtrar el historial de los 500 registros buscando solo esa máquina
    df_hist_individual = df_base[df_base[COL_TELAR] == telar_hist_sel].copy()
    
    if not df_hist_individual.empty:
        # Creamos una columna de texto que junte la Fecha y el Turno para el eje X
        df_hist_individual['Eje_Tiempo'] = df_hist_individual[COL_FECHA].dt.strftime('%d/%m/%Y') + " - " + df_hist_individual[COL_TURNO]
        
        # Gráfico de líneas continuo con ambas series
        fig_linea_tecnico = px.line(
            df_hist_individual,
            x='Eje_Tiempo',
            y=['U/CMPX', 'T/CMPX'], # <- Añadida la serie T/CMPX aquí en la lista
            title=f"Evolución Cronológica de Parámetros Técnicos - Telar {telar_hist_sel}",
            labels={'Eje_Tiempo': "Línea de Tiempo (Fecha - Turno)", 'value': "Valor Coeficiente", 'variable': "Parámetro"},
            markers=True, # Dibuja puntos en cada intersección
            color_discrete_sequence=["#059669", "#D97706"] # Verde para Urdido y Naranja para Trama
        )
        
        fig_linea_tecnico.update_layout(xaxis_tickangle=-45, hovermode="x unified")
        st.plotly_chart(fig_linea_tecnico, use_container_width=True)


        with st.expander("🔍 Detalles ▼"):


            columnas_visibles = [COL_FECHA, COL_TURNO, COL_TELAR,COL_EFICIENCIA, COL_URD, 'U/CMPX',COL_TRAMA,'T/CMPX']
            st.dataframe(df_turno_completo[columnas_visibles], use_container_width=True)


    else:
        st.info("La máquina seleccionada no registra actividad en este bloque temporal.")
