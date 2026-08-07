import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Configuración de página de Streamlit
st.set_page_config(page_title="Control de Pagos Mensuales", page_icon="💰", layout="wide")

# Conexión a Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.title("📊 Control de Pagos y Finanzas Mensuales")

# --- SELECTOR DE MES Y AÑO ---
col_mes, col_anio = st.columns(2)
meses = ["FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]

with col_mes:
    mes_seleccionado = st.selectbox("Selecciona el Mes:", meses, index=6) # Agosto por defecto

with col_anio:
    anio_seleccionado = st.selectbox("Selecciona el Año:", [2026, 2027], index=0)

st.divider()

# --- CARGAR DATOS DE SUPABASE ---
def obtener_pagos_fijos():
    res = supabase.table("pagos_fijos").select("*").execute()
    return pd.DataFrame(res.data)

def obtener_historial_mes(mes, anio):
    res = supabase.table("historial_pagos").select("*").eq("mes", mes).eq("anio", anio).execute()
    return pd.DataFrame(res.data)

def obtener_otros_pagos_mes(mes, anio):
    res = supabase.table("otros_pagos").select("*").eq("mes", mes).eq("anio", anio).execute()
    return pd.DataFrame(res.data)

df_fijos = obtener_pagos_fijos()
df_historial = obtener_historial_mes(mes_seleccionado, anio_seleccionado)
df_otros = obtener_otros_pagos_mes(mes_seleccionado, anio_seleccionado)

# Si el mes no tiene registros inicializados, crearlos automáticamente desde pagos_fijos
if df_historial.empty and not df_fijos.empty:
    registros_nuevos = [
        {"pago_fijo_id": row["id"], "mes": mes_seleccionado, "anio": anio_seleccionado, "monto": row["monto_defecto"], "estado": "PENDIENTE"}
        for _, row in df_fijos.iterrows()
    ]
    supabase.table("historial_pagos").insert(registros_nuevos).execute()
    df_historial = obtener_historial_mes(mes_seleccionado, anio_seleccionado)

# Unir catálogo fijo con el historial del mes
if not df_historial.empty and not df_fijos.empty:
    df_completo = pd.merge(df_fijos, df_historial, left_on="id", right_on="pago_fijo_id", suffixes=("_base", "_mes"))
else:
    df_completo = pd.DataFrame()

# --- MÉTRICAS / TARJETAS (CÁLCULO AUTOMÁTICO) ---
monto_fijo_pendiente = df_completo[df_completo["estado"] == "PENDIENTE"]["monto"].sum() if not df_completo.empty else 0
monto_otros_pendiente = df_otros[df_otros["estado"] == "PENDIENTE"]["monto"].sum() if not df_otros.empty else 0
monto_fijo_pagado = df_completo[df_completo["estado"] == "PAGADO"]["monto"].sum() if not df_completo.empty else 0
monto_otros_pagado = df_otros[df_otros["estado"] == "PAGADO"]["monto"].sum() if not df_otros.empty else 0

total_necesito_conseguir = monto_fijo_pendiente + monto_otros_pendiente
total_pagado = monto_fijo_pagado + monto_otros_pagado

c1, c2, c3 = st.columns(3)
c1.metric("🎯 NECESITO CONSEGUIR", f"${total_necesito_conseguir:,.2f}")
c2.metric("✅ TOTAL PAGADO", f"${total_pagado:,.2f}")
c3.metric("📌 TOTAL PROYECTADO DEL MES", f"${(total_necesito_conseguir + total_pagado):,.2f}")

st.divider()

# --- SECCIÓN 1: PAGOS FIJOS MENSUALES ---
st.subheader("1. Pagos Fijos Mensuales")

if not df_completo.empty:
    for idx, row in df_completo.iterrows():
        col_nom, col_monto, col_estado, col_btn = st.columns([3, 2, 2, 2])
        col_nom.write(f"**{row['nombre']}**")
        col_monto.write(f"${row['monto']:.2f}")
        
        estado_actual = row["estado"]
        if estado_actual == "PAGADO":
            col_estado.success("PAGADO")
            if col_btn.button("Marcar Pendiente", key=f"fijo_p_{row['id_mes']}"):
                supabase.table("historial_pagos").update({"estado": "PENDIENTE"}).eq("id", row["id_mes"]).execute()
                st.rerun()
        else:
            col_estado.warning("PENDIENTE")
            if col_btn.button("Marcar Pagado", key=f"fijo_c_{row['id_mes']}"):
                supabase.table("historial_pagos").update({"estado": "PAGADO"}).eq("id", row["id_mes"]).execute()
                st.rerun()

st.divider()

# --- SECCIÓN 2: OTROS PAGOS (PRÉSTAMOS EXPRÉS / EMERGENTES) ---
st.subheader("2. OTROS PAGOS (Préstamos / Gastos Emergentes)")

# Formulario para agregar un gasto emergente nuevo
with st.expander("➕ Agregar nuevo préstamo o pago emergente"):
    with st.form("form_nuevo_otro"):
        desc = st.text_input("Descripción del pago (Ej: Préstamo exprés):")
        monto_ingresado = st.number_input("Monto en $:", min_value=0.0, step=1.0)
        submit = st.form_submit_button("Guardar Pago")
        
        if submit and desc and monto_ingresado > 0:
            supabase.table("otros_pagos").insert({
                "descripcion": desc,
                "monto": monto_ingresado,
                "mes": mes_seleccionado,
                "anio": anio_seleccionado,
                "estado": "PENDIENTE"
            }).execute()
            st.success("Pago agregado correctamente")
            st.rerun()

if not df_otros.empty:
    for idx, row in df_otros.iterrows():
        col_nom, col_monto, col_estado, col_btn = st.columns([3, 2, 2, 2])
        col_nom.write(f"**{row['descripcion']}**")
        col_monto.write(f"${row['monto']:.2f}")
        
        if row["estado"] == "PAGADO":
            col_estado.success("PAGADO")
            if col_btn.button("Marcar Pendiente", key=f"otro_p_{row['id']}"):
                supabase.table("otros_pagos").update({"estado": "PENDIENTE"}).eq("id", row["id"]).execute()
                st.rerun()
        else:
            col_estado.warning("PENDIENTE")
            if col_btn.button("Marcar Pagado", key=f"otro_c_{row['id']}"):
                supabase.table("otros_pagos").update({"estado": "PAGADO"}).eq("id", row["id"]).execute()
                st.rerun()
else:
    st.info("No hay pagos emergentes registrados para este mes.")