import streamlit as st
import pandas as pd
import plotly.express as px
import copy
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import io
import tempfile

# Configuración avanzada de la interfaz de usuario
st.set_page_config(page_title="Optimizador de Deuda a Inversión", layout="wide")

st.title("🚀 Sistema de Optimización Financiera: Deuda a Inversión")
st.write(
    "Este sistema aplica el **Método Avalancha** para minimizar el pago de intereses "
    "y redirige automáticamente el flujo de caja liberado hacia un portafolio de inversión estructurado."
)

# Inicializar el estado de la sesión para almacenar deudas si no existe
if 'deudas' not in st.session_state:
    st.session_state.deudas = [
        # Ejemplos por defecto para facilitar las pruebas locales
        {"Deuda": "Tarjeta de Crédito A", "Saldo": 5000.0, "Tasa (%)": 28.5, "Pago Mínimo": 200.0},
        {"Deuda": "Crédito de Vehículo", "Saldo": 15000.0, "Tasa (%)": 14.2, "Pago Mínimo": 450.0},
        {"Deuda": "Crédito Libre Inversión", "Saldo": 8000.0, "Tasa (%)": 18.9, "Pago Mínimo": 250.0}
    ]

# --- SECCIÓN 1: PANEL DE CONTROL DE ENTRADAS ---
st.sidebar.header("🎛️ Configuración de Parámetros")

st.sidebar.subheader("Flujo de Caja Mensual")
ingresos = st.sidebar.number_input("Ingresos Mensuales Totales ($)", min_value=0.0, value=4500.0, step=100.0)
gastos = st.sidebar.number_input("Gastos Fijos (Sin deudas) ($)", min_value=0.0, value=2000.0, step=100.0)
flujo_disponible_inicial = ingresos - gastos

st.sidebar.subheader("Parámetros de Inversión")
meses_proyeccion = st.sidebar.slider("Horizonte de Proyección (Meses)", min_value=12, max_value=120, value=60, step=6)
tasa_retorno_anual = st.sidebar.number_input("Rendimiento Anual Estimado ETF (%)", min_value=0.0, value=9.5, step=0.5)

# --- SECCIÓN 2: GESTIÓN DE DEUDAS ---
col_form, col_tabla = st.columns([1, 2])

with col_form:
    st.subheader("📝 Añadir Pasivos")
    with st.form("formulario_deuda", clear_on_submit=True):
        nombre = st.text_input("Nombre de la Obligación")
        saldo = st.number_input("Saldo Pendiente Actual ($)", min_value=0.0, step=500.0)
        tasa = st.number_input("Tasa de Interés Nominal Anual (%)", min_value=0.0, step=0.5)
        pago_min = st.number_input("Pago Mínimo Mensual Requerido ($)", min_value=0.0, step=50.0)
        
        btn_agregar = st.form_submit_button("Agregar a la Lista")
        if btn_agregar and nombre and saldo > 0:
            st.session_state.deudas.append({
                "Deuda": nombre, "Saldo": saldo, "Tasa (%)": tasa, "Pago Mínimo": pago_min
            })
            st.success(f"'{nombre}' registrada.")

with col_tabla:
    st.subheader("📋 Estado Actual de Deudas")
    if st.session_state.deudas:
        df_actual = pd.DataFrame(st.session_state.deudas)
        st.dataframe(df_actual, use_container_width=True)
        
        if st.button("🗑️ Limpiar todas las deudas"):
            st.session_state.deudas = []
            st.rerun()
    else:
        st.info("No hay deudas registradas. Todo tu flujo disponible se destinará directamente a inversión.")

# --- SECCIÓN 3: ALGORITMO DE AMORTIZACIÓN Y REDIRECCIÓN ---
def simular_estrategia(flujo_inicial, lista_deudas, meses, rendimiento_inv):
    # Copia profunda para no alterar los datos originales del session_state
    deudas = copy.deepcopy(lista_deudas)
    rendimiento_mensual_inv = (rendimiento_inv / 100) / 12
    
    # Estructuras para almacenar el histórico mes a mes
    historico = []
    saldo_inversion = 0.0
    total_intereses_pagados = 0.0
    
    for mes in range(1, meses + 1):
        # 1. Calcular intereses del mes actual y actualizar saldos
        interes_mes_total = 0.0
        deudas_activas = [d for d in deudas if d["Saldo"] > 0]
        
        for d in deudas_activas:
            tasa_mensual = (d["Tasa (%)"] / 100) / 12
            interes_de_este_mes = d["Saldo"] * tasa_mensual
            d["Saldo"] += interes_de_este_mes
            interes_mes_total += interes_de_este_mes
            total_intereses_pagados += interes_de_este_mes

        # 2. Determinar la capacidad de pago requerida para mínimos
        pago_minimo_requerido = sum(d["Pago Mínimo"] for d in deudas_activas)
        
        # Validar viabilidad financiera preliminar
        if flujo_inicial < pago_minimo_requerido and deudas_activas:
            return "ERROR_FLUJO_INSUFICIENTE", pago_minimo_requerido
            
        # El acelerador financiero es el flujo libre que queda tras apartar los mínimos necesarios
        caja_para_acelerar = flujo_inicial - pago_minimo_requerido
        
        # 3. Ejecutar pagos mínimos obligatorios
        for d in deudas_activas:
            pago = min(d["Pago Mínimo"], d["Saldo"])
            d["Saldo"] -= pago
            # Si el pago mínimo fue mayor que el saldo remanente, el sobrante regresa al acelerador
            caja_para_acelerar += (d["Pago Mínimo"] - pago)

        # 4. Aplicar Método Avalancha con el excedente (Caja para acelerar)
        # Ordenar deudas activas de mayor a menor tasa de interés
        deudas_ordenadas = sorted([d for d in deudas if d["Saldo"] > 0], key=lambda x: x["Tasa (%)"], reverse=True)
        
        for d in deudas_ordenadas:
            if caja_para_acelerar <= 0:
                break
            pago_extra = min(caja_para_acelerar, d["Saldo"])
            d["Saldo"] -= pago_extra
            caja_para_acelerar -= pago_extra

        # 5. Fase de Inversión: Si sobra flujo de caja (deudas liquidadas), se va a ETFs
        capital_a_invertir = 0.0
        if not [d for d in deudas if d["Saldo"] > 0]:
            # Si no hay deudas, todo el flujo de caja disponible más el remanente se invierte
            capital_a_invertir = flujo_inicial + caja_para_acelerar
            saldo_inversion += capital_a_invertir
        
        # Aplicar el efecto del interés compuesto mensual al portafolio
        interes_ganado_inv = saldo_inversion * rendimiento_mensual_inv
        saldo_inversion += interes_ganado_inv
        
        # Registrar métricas del mes actual para las gráficas
        registro_mes = {
            "Mes": mes,
            "Saldo Inversión ($)": saldo_inversion,
            "Intereses Pagados ($)": interes_mes_total,
            "Capital Invertido este Mes ($)": capital_a_invertir
        }
        # Guardar el saldo individual de cada deuda para trazar la curva de descenso
        for d in deudas:
            registro_mes[d["Deuda"]] = max(0.0, d["Saldo"])
            
        historico.append(registro_mes)
        
    return pd.DataFrame(historico), total_intereses_pagados

# --- SECCIÓN 4: PROCESAMIENTO Y DASHBOARD ---
st.divider()
st.header("📊 Diagnóstico y Proyección Financiera")

# Ejecutar la simulación si existen deudas o flujo configurado
resultado, info_adicional = simular_estrategia(flujo_disponible_inicial, st.session_state.deudas, meses_proyeccion, tasa_retorno_anual)

if isinstance(resultado, str) and resultado == "ERROR_FLUJO_INSUFICIENTE":
    st.error(
        f"⚠️ **Déficit de Flujo de Caja:** Tus pagos mínimos requeridos (${info_adicional:,.2f}) "
        f"superan tu capacidad mensual disponible (${flujo_disponible_inicial:,.2f}). "
        f"Es necesario reducir gastos fijos o reestructurar pasivos para liberar margen operativo."
    )
else:
    df_resultados = resultado
    
    # Determinar métricas clave
    columnas_deudas = [d["Deuda"] for d in st.session_state.deudas]
    df_resultados["Deuda Total ($)"] = df_resultados[columnas_deudas].sum(axis=1) if columnas_deudas else 0.0
    
    # Encontrar el mes exacto de libertad de deuda (Deuda Total == 0)
    mes_libertad = df_resultados[df_resultados["Deuda Total ($)"] == 0]["Mes"].min()
    mes_libertad_texto = f"Mes {mes_libertad}" if not pd.isna(mes_libertad) else f"Más de {meses_proyeccion} meses"
    
    patrimonio_final = df_resultados["Saldo Inversión ($)"].iloc[-1]
    
    # Desplegar KPIs principales
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric("Flujo de Caja Libre Inicial", f"${flujo_disponible_inicial:,.2f}")
    with kpi2:
        st.metric("Mes de Salida de Deudas (Avalancha)", mes_libertad_texto, delta="Optimizado", delta_color="inverse")
    with kpi3:
        st.metric(f"Portafolio Proyectado (Mes {meses_proyeccion})", f"${patrimonio_final:,.2f}")

    # --- VISUALIZACIONES ---
    st.subheader("📈 Curva de Transición Finanzas Personales")

    # --- NUEVA GRÁFICA: EL EFECTO AVALANCHA ---
    st.write(
        "**Entendiendo el Método Avalancha:** Observa cómo el excedente de capital ataca agresivamente "
        "la obligación con la tasa de interés más alta hasta destruirla. Al liquidarla, ese pago se suma al excedente "
        "para derribar la siguiente deuda de forma acelerada."
    )
    
    # Extraer los nombres de las deudas para filtrar el DataFrame
    columnas_deudas = [d["Deuda"] for d in st.session_state.deudas]
    
    if columnas_deudas:
        # Preparar los datos específicamente para el gráfico de avalancha
        df_avalancha = df_resultados[["Mes"] + columnas_deudas].copy()
        
        # Transformar los datos (Melt) para que Plotly pueda apilarlos por color
        df_avalancha_melted = df_avalancha.melt(
            id_vars=["Mes"], 
            value_vars=columnas_deudas, 
            var_name="Obligación", 
            value_name="Saldo Pendiente ($)"
        )
        
        # Crear el gráfico de áreas apiladas
        fig_avalancha = px.area(
            df_avalancha_melted, 
            x="Mes", 
            y="Saldo Pendiente ($)", 
            color="Obligación",
            title="Desglose del Efecto Avalancha por Obligación",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        
        # Ajustes visuales
        fig_avalancha.update_layout(hovermode="x unified")
        
        st.plotly_chart(fig_avalancha, use_container_width=True)
        st.divider()

    with st.expander("📚 ¿Por qué matemáticamente funciona el Método Avalancha?"):
        st.write("""
        A diferencia del Método Bola de Nieve (que ataca la deuda más pequeña primero para ganar motivación psicológica), 
        el **Método Avalancha** es la estrategia matemáticamente óptima para retener la mayor cantidad de tu capital.
        
        * **Regla 1:** Pagas el mínimo exigido en todas tus obligaciones para no dañar tu historial crediticio.
        * **Regla 2:** Identificas la deuda que te cobra el mayor interés porcentual (Tasa Anual).
        * **Regla 3:** Inyectas todo tu flujo de caja libre excedente únicamente a esa deuda tóxica.
        
        Al eliminar primero el pasivo más costoso, detienes la "hemorragia" de intereses, acortando el tiempo total 
        para quedar libre de deudas y maximizando el capital que luego irá a tu portafolio de inversión.
        """)
    
    # Crear un DataFrame enfocado en la transición Deuda vs Inversión
    df_vis = df_resultados[["Mes", "Deuda Total ($)", "Saldo Inversión ($)"]].copy()
    df_melted = df_vis.melt(id_vars=["Mes"], value_vars=["Deuda Total ($)", "Saldo Inversión ($)"], 
                            var_name="Concepto", value_name="Monto ($)")
    
    fig_transicion = px.line(df_melted, x="Mes", y="Monto ($)", color="Concepto",
                             title="Intercambio de Pasivos por Activos en el Tiempo",
                             color_discrete_sequence=["#EF553B", "#636EFA"])
    st.plotly_chart(fig_transicion, use_container_width=True)

    # --- NUEVA GRÁFICA: APORTES MENSUALES ---
    # --- NUEVA GRÁFICA: MAGIA DEL INTERÉS COMPUESTO ---
    st.divider()
    st.subheader("🌱 Crecimiento del Portafolio: Capital vs. Rendimientos")
    st.write(
        "Esta gráfica desglosa el valor total de tu portafolio en dos partes: el dinero real que ha "
        "salido de tu bolsillo (Capital Aportado) y el crecimiento generado por el mercado (Interés Compuesto)."
    )
    
    # 1. Calcular las métricas acumuladas
    df_resultados['Capital Aportado Acumulado ($)'] = df_resultados['Capital Invertido este Mes ($)'].cumsum()
    df_resultados['Ganancia Acumulada ($)'] = df_resultados['Saldo Inversión ($)'] - df_resultados['Capital Aportado Acumulado ($)']
    
    # 2. Filtrar para mostrar solo los meses donde ya comenzó la inversión
    df_inversion = df_resultados[df_resultados['Saldo Inversión ($)'] > 0].copy()
    
    if not df_inversion.empty:
        # 3. Transformar los datos para poder apilarlos en Plotly
        df_inv_melted = df_inversion.melt(
            id_vars=["Mes"],
            value_vars=["Capital Aportado Acumulado ($)", "Ganancia Acumulada ($)"],
            var_name="Componente",
            value_name="Monto ($)"
        )
        
        # 4. Crear un gráfico de barras apiladas (Stacked Bar Chart)
        fig_crecimiento = px.bar(
            df_inv_melted,
            x="Mes",
            y="Monto ($)",
            color="Componente",
            title="Evolución del Patrimonio en el Tiempo",
            color_discrete_map={
                "Capital Aportado Acumulado ($)": "#00CC96", # Verde para el aporte real
                "Ganancia Acumulada ($)": "#636EFA"          # Azul brillante para la ganancia del ETF
            }
        )
        
        # Ajustes visuales para una lectura limpia
        fig_crecimiento.update_layout(
            barmode='stack', 
            hovermode="x unified",
            xaxis_title="Mes de Proyección",
            yaxis_title="Valor del Portafolio ($)"
        )
        
        st.plotly_chart(fig_crecimiento, use_container_width=True)
    else:
        st.info("La proyección actual no alcanza la fase de inversión. Incrementa el horizonte de meses o el flujo de caja.")

    # Desglose de inversión por ETFs recomendados
    if patrimonio_final > 0:
        st.divider()
        st.header("🎯 Estructura Estratégica del Portafolio de Inversión")
        st.write("Distribución del capital liberado según la estrategia de crecimiento y valor diversificado:")
        
        # Pesos del portafolio objetivo
        distribucion_etfs = [
            {"ETF": "SPYG (S&P 500 Growth)", "Porcentaje": 35, "Asignación Final ($)": patrimonio_final * 0.35, "Enfoque": "Crecimiento de empresas de gran capitalización americana."},
            {"ETF": "SMH (Semiconductor Index)", "Porcentaje": 20, "Asignación Final ($)": patrimonio_final * 0.20, "Enfoque": "Exposición de alta convicción a tecnología y hardware avanzado."},
            {"ETF": "BRK.B (Berkshire Hathaway)", "Porcentaje": 20, "Asignación Final ($)": patrimonio_final * 0.20, "Enfoque": "Anclaje de valor, resiliencia y diversificación industrial."},
            {"ETF": "IEMG (Core MSCI Emerging Markets)", "Porcentaje": 20, "Asignación Final ($)": patrimonio_final * 0.20, "Enfoque": "Captura de valor geográfico en mercados emergentes de alta expansión."},
            {"ETF": "VTI (Total Stock Market)", "Porcentaje": 5, "Asignación Final ($)": patrimonio_final * 0.05, "Enfoque": "Cobertura total del ecosistema de renta variable en EE. UU."}
        ]
        
        df_etfs = pd.DataFrame(distribucion_etfs)
        
        col_pie, col_tabla_etf = st.columns([1, 1])
        with col_pie:
            fig_pie = px.pie(df_etfs, values='Porcentaje', names='ETF', 
                             title="Distribución de Activos",
                             color_discrete_sequence=px.colors.sequential.YlGnBu_r)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_tabla_etf:
            st.dataframe(
                df_etfs,
                use_container_width=True,
                hide_index=True
            )


st.divider()
st.header("📩 Recibe tu Plan de Optimización por Correo")
st.write("Ingresa tu correo para recibir un resumen en PDF con tu mes de libertad financiera y la proyección de tu portafolio.")

correo_usuario = st.text_input("Tu correo electrónico:")

if st.button("Generar y Enviar PDF"):
    if correo_usuario and "df_resultados" in locals(): # Asegurarnos de que la simulación se ejecutó
        with st.spinner('Generando reporte y enviando...'):
            try:                
                # --- 1. PREPARAR IMÁGENES CON KALEIDO ---
                import kaleido
                import tempfile
                
                # Creamos los archivos temporales primero
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_transicion, \
                     tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_crecimiento:
                    
                    img_transicion = tmp_transicion.name
                    img_crecimiento = tmp_crecimiento.name
                    
                    # Intentamos generar las imágenes
                    try:
                        fig_transicion.write_image(img_transicion, engine="kaleido")
                        fig_crecimiento.write_image(img_crecimiento, engine="kaleido")
                    except Exception as e:
                        # Si falla, avisamos al usuario pero el PDF se genera con el resto de datos
                        st.warning("No se pudieron generar las gráficas en el PDF.")
                        # Opcional: imprimir el error en la terminal para depurar
                        # print(f"Error generando imágenes: {e}")

                # --- 2. CREAR EL PDF AVANZADO ---
                pdf = FPDF()
                pdf.add_page()
                
                # Encabezado Principal
                pdf.set_font("Arial", style="B", size=18)
                pdf.set_text_color(43, 232, 168) # Verde de tu marca
                pdf.cell(200, 10, txt="Plan de Optimizacion: Deuda a Inversion", ln=True, align='C')
                pdf.set_text_color(0, 0, 0) # Volver a negro
                pdf.ln(8)
                
                # Sección A: Datos Ingresados
                pdf.set_font("Arial", style="B", size=12)
                pdf.cell(200, 10, txt="1. Tu Situacion Actual", ln=True)
                pdf.set_font("Arial", size=11)
                pdf.cell(200, 7, txt=f"Ingresos Mensuales: ${ingresos:,.2f}", ln=True)
                pdf.cell(200, 7, txt=f"Gastos Fijos (Sin deudas): ${gastos:,.2f}", ln=True)
                pdf.cell(200, 7, txt=f"Flujo de Caja Libre Inicial: ${flujo_disponible_inicial:,.2f}", ln=True)
                pdf.ln(5)
                
                # Sección B: Deudas
                pdf.set_font("Arial", style="B", size=12)
                pdf.cell(200, 10, txt="2. Obligaciones a Liquidar (Metodo Avalancha)", ln=True)
                pdf.set_font("Arial", size=10)
                if st.session_state.deudas:
                    for d in st.session_state.deudas:
                        pdf.cell(200, 6, txt=f"- {d['Deuda']}: Saldo ${d['Saldo']:,.2f} | Tasa: {d['Tasa (%)']}% | Min: ${d['Pago Mínimo']:,.2f}", ln=True)
                else:
                    pdf.cell(200, 6, txt="No registraste deudas. Todo tu flujo va directo a inversion.", ln=True)
                pdf.ln(8)
                
                # Sección C: Proyección Final
                pdf.set_font("Arial", style="B", size=12)
                pdf.cell(200, 10, txt="3. Tu Proyeccion Estrategica", ln=True)
                pdf.set_font("Arial", size=11)
                pdf.cell(200, 7, txt=f"Mes de Libertad Financiera (Cero Deudas): {mes_libertad_texto}", ln=True)
                pdf.cell(200, 7, txt=f"Patrimonio Total Estimado (Mes {meses_proyeccion}): ${patrimonio_final:,.2f}", ln=True)
                
                # Sección D: Gráficas
                # Agregamos una nueva página para que las gráficas se vean grandes y limpias
                pdf.add_page()
                pdf.set_font("Arial", style="B", size=14)
                pdf.cell(200, 10, txt="4. Transicion: Deuda vs Inversion", ln=True)
                # Insertar la gráfica de transición
                pdf.image(img_transicion, x=10, y=None, w=190)
                
                pdf.ln(10)
                pdf.cell(200, 10, txt="5. Crecimiento Patrimonial (Interes Compuesto)", ln=True)
                # Insertar la gráfica de crecimiento
                pdf.image(img_crecimiento, x=10, y=None, w=190)
                
                # Guardar PDF en memoria para adjuntarlo al correo
                pdf_buffer = io.BytesIO()
                pdf_output = pdf.output(dest='S').encode('latin1')
                pdf_buffer.write(pdf_output)
                pdf_buffer.seek(0)

                # --- 2. CONFIGURAR EL CORREO ---
                # NOTA: Debes usar un App Password si usas Gmail
                remitente = "alejo1109@gmail.com" 
                password = st.secrets["EMAIL_PASSWORD"] 

                msg = MIMEMultipart()
                msg['From'] = remitente
                msg['To'] = correo_usuario
                msg['Subject'] = "Tu Plan de Optimización de Deuda a Inversión"
                
                cuerpo = "Hola,\n\nAdjunto encontrarás el resumen de tu proyección financiera.\n\n¡Sigue construyendo tu patrimonio!"
                msg.attach(MIMEText(cuerpo, 'plain'))

                # --- 3. ADJUNTAR EL PDF ---
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(pdf_buffer.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="Plan_Financiero.pdf"')
                msg.attach(part)

                # --- 4. ENVIAR VIA SMTP (Ejemplo con Gmail) ---
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(remitente, password)
                text = msg.as_string()
                server.sendmail(remitente, correo_usuario, text)
                server.quit()

                st.success(f"¡Reporte enviado exitosamente a {correo_usuario}!")

            except Exception as e:
                st.error(f"Hubo un error al enviar el correo: {e}")
    else:
        st.warning("Por favor ingresa un correo válido y asegúrate de ejecutar la simulación primero.")
