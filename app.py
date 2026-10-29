import streamlit as st
from supabase import create_client, Client
import datetime
import pandas as pd

# Configuración de Página
st.set_page_config(page_title="InDrive Contabilidad", page_icon="🏍️", layout="centered")

# Fecha de HOY en zona horaria Nicaragua (UTC-6)
def obtener_fecha_hoy():
    tz_nicaragua = datetime.timezone(datetime.timedelta(hours=-6))
    return datetime.datetime.now(tz_nicaragua).date()

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}

CATEGORIAS_GASTOS = [
    "Recarga InDrive", 
    "Gasolina", 
    "Agua", 
    "Gaseosa o jugo", 
    "Comida en calle", 
    "Antojo de dulce"
]

# Conexión a Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# Rango Semanal: Inicia el DOMINGO y termina el SÁBADO
def obtener_rango_semanal(fecha_ref):
    idx = (fecha_ref.weekday() + 1) % 7  # Domingo = 0
    inicio = fecha_ref - datetime.timedelta(days=idx)
    fin = inicio + datetime.timedelta(days=6)
    return inicio, fin

# Diálogo para Confirmar Retiro de Fondo
@st.dialog("Confirmar Retiro de Fondo")
def confirmar_retirar_fondo(fondo_id, fondo_nombre):
    st.write(f"¿Deseas retirar y reiniciar el acumulado del fondo **{fondo_nombre}** a C$ 0.00?")
    c_si, c_no = st.columns(2)
    if c_si.button("Sí, Retirar", key=f"yes_{fondo_id}"):
        supabase.table("acumuladores").update({"saldo": 0.00}).eq("id", fondo_id).execute()
        st.success(f"Fondo **{fondo_nombre}** retirado con éxito.")
        st.rerun()
    if c_no.button("No, Cancelar", key=f"no_{fondo_id}"):
        st.rerun()

# Título
st.title("🏍️ InDrive Contabilidad")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 Registrar Día", 
    "📊 Resumen Semanal", 
    "💰 Distribución de Ganancias", 
    "🎯 Objetivos",
    "📈 Reportes"
])

# ------------------------------------------------------------------------------
# PESTAÑA 1: REGISTRAR DÍA
# ------------------------------------------------------------------------------
with tab1:
    st.header("📝 Registro Diario De Operaciones")
    fecha_seleccionada = st.date_input("Fecha De Registro", obtener_fecha_hoy())

    res_v_dia = supabase.table("viajes").select("*").eq("fecha", str(fecha_seleccionada)).order("numero_viaje").execute()
    viajes_existentes = [v["numero_viaje"] for v in res_v_dia.data] if res_v_dia.data else []
    siguiente_numero_viaje = max(viajes_existentes, default=0) + 1

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Registrar Nuevo Viaje")
        with st.form("form_viaje", clear_on_submit=True):
            st.text_input("Número De Viaje", value=f"Viaje #{siguiente_numero_viaje}", disabled=True)
            monto_viaje = st.number_input("Valor Pagado (C$)", min_value=0.0, step=10.0)
            propina = st.number_input("Propina (C$)", min_value=0.0, step=5.0)
            btn_viaje = st.form_submit_button("Guardar Viaje")
            
            if btn_viaje:
                supabase.table("viajes").insert({
                    "fecha": str(fecha_seleccionada),
                    "numero_viaje": siguiente_numero_viaje,
                    "monto": monto_viaje,
                    "propina": propina
                }).execute()
                st.success(f"Viaje #{siguiente_numero_viaje} Registrado.")
                st.rerun()

    with col2:
        st.subheader("Registrar Nuevo Gasto")
        with st.form("form_gasto", clear_on_submit=True):
            categoria = st.selectbox("Categoría De Gasto", CATEGORIAS_GASTOS)
            monto_gasto = st.number_input("Monto Del Gasto (C$)", min_value=0.0, step=10.0)
            descripcion = st.text_input("Descripción (Opcional)")
            btn_gasto = st.form_submit_button("Guardar Gasto")
            
            if btn_gasto:
                supabase.table("gastos").insert({
                    "fecha": str(fecha_seleccionada),
                    "categoria": categoria,
                    "monto": monto_gasto,
                    "descripcion": descripcion
                }).execute()
                st.success("Gasto Registrado.")
                st.rerun()

    st.divider()
    st.subheader(f"Detalle Del Día ({fecha_seleccionada.strftime('%d/%m/%Y')})")
    
    col_v, col_g = st.columns(2)
    with col_v:
        st.write("**Viajes Del Día**")
        if res_v_dia.data:
            df_v_hoy = pd.DataFrame(res_v_dia.data)
            df_v_hoy["Monto (C$)"] = df_v_hoy["monto"].astype(float)
            df_v_hoy["Propina (C$)"] = df_v_hoy["propina"].astype(float)
            df_v_hoy["Total Viaje (C$)"] = df_v_hoy["Monto (C$)"] + df_v_hoy["Propina (C$)"]
            df_v_hoy["Viaje"] = df_v_hoy["numero_viaje"].apply(lambda x: f"Viaje #{x}")
            
            st.dataframe(df_v_hoy[["Viaje", "Monto (C$)", "Propina (C$)", "Total Viaje (C$)"]], use_container_width=True, hide_index=True)
            total_colectado_dia = df_v_hoy["Total Viaje (C$)"].sum()
            st.markdown(f"**Total Viajes:** `{len(df_v_hoy)}` | **Ingreso Día:** `C$ {total_colectado_dia:.2f}`")
        else:
            st.caption("Sin viajes registrados hoy.")
            
    with col_g:
        st.write("**Gastos Del Día**")
        res_g_dia = supabase.table("gastos").select("*").eq("fecha", str(fecha_seleccionada)).execute()
        if res_g_dia.data:
            df_g_hoy = pd.DataFrame(res_g_dia.data)
            df_g_hoy["Monto (C$)"] = df_g_hoy["monto"].astype(float)
            df_g_hoy["Categoría"] = df_g_hoy["categoria"]
            
            st.dataframe(df_g_hoy[["Categoría", "Monto (C$)"]], use_container_width=True, hide_index=True)
            total_gastos_dia = df_g_hoy["Monto (C$)"].sum()
            st.markdown(f"**Total Gastos Hoy:** `C$ {total_gastos_dia:.2f}`")
        else:
            st.caption("Sin gastos registrados hoy.")

# ------------------------------------------------------------------------------
# PESTAÑA 2: RESUMEN SEMANAL
# ------------------------------------------------------------------------------
with tab2:
    st.header("📊 Resumen Semanal De Operaciones")
    
    hoy = obtener_fecha_hoy()
    inicio_sem, fin_sem = obtener_rango_semanal(hoy)
    
    st.subheader(f"Corte Semanal: {inicio_sem.strftime('%d/%m/%Y')} al {fin_sem.strftime('%d/%m/%Y')}")

    res_v_sem = supabase.table("viajes").select("monto, propina").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    df_v_sem = pd.DataFrame(res_v_sem.data) if res_v_sem.data else pd.DataFrame()
    ingresos_semana = float(df_v_sem["monto"].astype(float).sum() + df_v_sem["propina"].astype(float).sum()) if not df_v_sem.empty else 0.0

    res_g_sem = supabase.table("gastos").select("monto").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    df_g_sem = pd.DataFrame(res_g_sem.data) if res_g_sem.data else pd.DataFrame()
    gastos_semana = float(df_g_sem["monto"].astype(float).sum()) if not df_g_sem.empty else 0.0

    ganancia_semana = ingresos_semana - gastos_semana

    m1, m2, m3 = st.columns(3)
    m1.metric("Ingresos Semana", f"C$ {ingresos_semana:.2f}")
    m2.metric("Gastos Semana", f"C$ {gastos_semana:.2f}")
    m3.metric("Ganancia Neta", f"C$ {ganancia_semana:.2f}")

    st.divider()
    st.subheader("📅 Desglose Diario")
    
    dias_semana_lista = []
    fecha_iter = inicio_sem
    
    res_v_todos = supabase.table("viajes").select("fecha, monto, propina").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    res_g_todos = supabase.table("gastos").select("fecha, monto").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    
    df_v_todos = pd.DataFrame(res_v_todos.data) if res_v_todos.data else pd.DataFrame()
    df_g_todos = pd.DataFrame(res_g_todos.data) if res_g_todos.data else pd.DataFrame()

    while fecha_iter <= fin_sem:
        f_str = str(fecha_iter)
        ing_dia = float(df_v_todos[df_v_todos["fecha"] == f_str][["monto", "propina"]].astype(float).sum().sum()) if not df_v_todos.empty and not df_v_todos[df_v_todos["fecha"] == f_str].empty else 0.0
        gas_dia = float(df_g_todos[df_g_todos["fecha"] == f_str]["monto"].astype(float).sum()) if not df_g_todos.empty and not df_g_todos[df_g_todos["fecha"] == f_str].empty else 0.0
        neto_dia = ing_dia - gas_dia
        
        nombre_dia = DIAS_SEMANA[fecha_iter.weekday()]
        
        dias_semana_lista.append({
            "Día": f"{nombre_dia} {fecha_iter.day}/{fecha_iter.month}",
            "Ingresos (C$)": f"{ing_dia:.2f}",
            "Gastos (C$)": f"{gas_dia:.2f}",
            "Ganancia Neta (C$)": f"{neto_dia:.2f}"
        })
        fecha_iter += datetime.timedelta(days=1)

    st.table(pd.DataFrame(dias_semana_lista))

# ------------------------------------------------------------------------------
# PESTAÑA 3: DISTRIBUCIÓN DE GANANCIAS
# ------------------------------------------------------------------------------
with tab3:
    st.header("💰 Distribución De Ganancias")
    
    hoy = obtener_fecha_hoy()
    inicio_sem, fin_sem = obtener_rango_semanal(hoy)

    # Ganancia Neta de HOY
    res_v_hoy = supabase.table("viajes").select("monto, propina").eq("fecha", str(hoy)).execute()
    res_g_hoy = supabase.table("gastos").select("monto").eq("fecha", str(hoy)).execute()
    ing_hoy = sum([float(x["monto"]) + float(x["propina"]) for x in res_v_hoy.data]) if res_v_hoy.data else 0.0
    gas_hoy = sum([float(x["monto"]) for x in res_g_hoy.data]) if res_g_hoy.data else 0.0
    neto_hoy = max(0.0, ing_hoy - gas_hoy)

    # Ganancia Neta SEMANAL
    res_v_sem = supabase.table("viajes").select("monto, propina").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    res_g_sem = supabase.table("gastos").select("monto").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    ing_sem = sum([float(x["monto"]) + float(x["propina"]) for x in res_v_sem.data]) if res_v_sem.data else 0.0
    gas_sem = sum([float(x["monto"]) for x in res_g_sem.data]) if res_g_sem.data else 0.0
    neto_sem = max(0.0, ing_sem - gas_sem)

    # Cargar fondos
    res_fondos = supabase.table("acumuladores").select("*").order("id").execute()
    fondos = res_fondos.data if res_fondos.data else []

    st.subheader(f"Ganancia Neta Hoy: C$ {neto_hoy:.2f} | Ganancia Neta Semana: C$ {neto_sem:.2f}")
    st.divider()

    c_h1, c_h2, c_h3, c_h4 = st.columns([3, 2, 2, 2])
    c_h1.write("**Fondo (%)**")
    c_h2.write("**Acumulado Hoy**")
    c_h3.write("**Acumulado Semana**")
    c_h4.write("**Acción**")
    st.divider()

    for f in fondos:
        pct = float(f.get("porcentaje", 0.0)) / 100.0
        nombre = f["nombre"]
        
        acum_hoy = neto_hoy * pct
        acum_semana = neto_sem * pct
        
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.write(f"**{nombre}** ({pct*100:.0f}%)")
        c2.write(f"C$ {acum_hoy:.2f}")
        c3.write(f"**C$ {acum_semana:.2f}**")
        
        if c4.button("Retirar", key=f"ret_{f['id']}"):
            confirmar_retirar_fondo(f["id"], nombre)

# ------------------------------------------------------------------------------
# PESTAÑA 4: OBJETIVOS DE AHORRO
# ------------------------------------------------------------------------------
with tab4:
    st.header("🎯 Objetivos De Ahorro Semanal")
    
    hoy = obtener_fecha_hoy()
    inicio_sem, fin_sem = obtener_rango_semanal(hoy)
    
    st.caption(f"Semana en curso: **Del {inicio_sem.strftime('%d/%m/%Y')} al {fin_sem.strftime('%d/%m/%Y')}**")

    # Formulario Crear / Editar Objetivo
    with st.expander("➕ / ✏️ Agregar o Editar Objetivo"):
        with st.form("form_objetivo", clear_on_submit=True):
            nombre_obj = st.text_input("Nombre del Objetivo (ej. Cuota de Moto)")
            monto_diario_obj = st.number_input("Monto de Objetivo Diario (C$)", min_value=0.0, step=50.0)
            dias_meta = st.number_input("Días a trabajar por semana", min_value=1, max_value=7, value=6)
            btn_obj = st.form_submit_button("Guardar Objetivo")
            
            if btn_obj and nombre_obj:
                try:
                    supabase.table("objetivos").insert({
                        "nombre": nombre_obj,
                        "monto_diario": monto_diario_obj,
                        "dias_semana": dias_meta
                    }).execute()
                    st.success("Objetivo Guardado Correctamente.")
                    st.rerun()
                except Exception:
                    st.error("Error al guardar. Asegúrate de haber creado la tabla 'objetivos' en Supabase.")

    st.divider()

    # Cálculo de Ganancia Neta Actual de la Semana
    res_v_sem = supabase.table("viajes").select("monto, propina").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    res_g_sem = supabase.table("gastos").select("monto").gte("fecha", str(inicio_sem)).lte("fecha", str(fin_sem)).execute()
    ing_sem = sum([float(x["monto"]) + float(x["propina"]) for x in res_v_sem.data]) if res_v_sem.data else 0.0
    gas_sem = sum([float(x["monto"]) for x in res_g_sem.data]) if res_g_sem.data else 0.0
    ganancia_neta_sem = max(0.0, ing_sem - gas_sem)

    # Mostrar Objetivos
    try:
        res_obj = supabase.table("objetivos").select("*").execute()
        if res_obj.data:
            for obj in res_obj.data:
                m_diario = float(obj["monto_diario"])
                d_trabajo = int(obj["dias_semana"])
                m_total_meta = m_diario * d_trabajo
                
                porcentaje_progreso = min(1.0, ganancia_neta_sem / m_total_meta) if m_total_meta > 0 else 0.0
                
                st.subheader(f"📌 {obj['nombre']}")
                st.progress(porcentaje_progreso)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Meta Diaria", f"C$ {m_diario:.2f}")
                c2.metric("Meta Semanal Total", f"C$ {m_total_meta:.2f}")
                c3.metric("Acumulado Neta Real", f"C$ {ganancia_neta_sem:.2f}")

                if st.button("🗑️ Eliminar Objetivo", key=f"del_obj_{obj['id']}"):
                    supabase.table("objetivos").delete().eq("id", obj["id"]).execute()
                    st.success("Objetivo Eliminado.")
                    st.rerun()
                st.divider()
        else:
            st.info("No tienes objetivos agregados aún. Usa la opción de arriba para crear uno.")
    except Exception:
        st.warning("Crea la tabla 'objetivos' en Supabase ejecutando el comando SQL que se indicó previamente.")

# ------------------------------------------------------------------------------
# PESTAÑA 5: REPORTES
# ------------------------------------------------------------------------------
with tab5:
    st.header("📈 Reportes Operativos")
    
    tipo_reporte = st.selectbox("Filtro De Reporte", ["Diario", "Semanal", "Mensual"])
    
    hoy = obtener_fecha_hoy()
    if tipo_reporte == "Diario":
        f_rep = st.date_input("Seleccionar Día", hoy)
        inicio_f, fin_f = f_rep, f_rep
    elif tipo_reporte == "Semanal":
        f_ref = st.date_input("Seleccionar Fecha", hoy)
        inicio_f, fin_f = obtener_rango_semanal(f_ref)
        st.caption(f"Del {inicio_f.strftime('%d/%m/%Y')} Al {fin_f.strftime('%d/%m/%Y')}")
    else:
        mes_sel = st.selectbox("Seleccionar Mes", list(MESES.values()), index=hoy.month - 1)
        num_mes = list(MESES.keys())[list(MESES.values()).index(mes_sel)]
        anio_sel = st.number_input("Año", min_value=2024, max_value=2030, value=hoy.year)
        inicio_f = datetime.date(anio_sel, num_mes, 1)
        fin_f = datetime.date(anio_sel, 12, 31) if num_mes == 12 else datetime.date(anio_sel, num_mes + 1, 1) - datetime.timedelta(days=1)

    res_v_rep = supabase.table("viajes").select("monto, propina").gte("fecha", str(inicio_f)).lte("fecha", str(fin_f)).execute()
    df_v_r = pd.DataFrame(res_v_rep.data) if res_v_rep.data else pd.DataFrame()
    ing_bruto = float(df_v_r["monto"].astype(float).sum()) if not df_v_r.empty and "monto" in df_v_r else 0.0
    propinas = float(df_v_r["propina"].astype(float).sum()) if not df_v_r.empty and "propina" in df_v_r else 0.0
    total_ingresos = ing_bruto + propinas

    res_g_rep = supabase.table("gastos").select("categoria, monto").gte("fecha", str(inicio_f)).lte("fecha", str(fin_f)).execute()
    df_g_r = pd.DataFrame(res_g_rep.data) if res_g_rep.data else pd.DataFrame()
    total_gastos = float(df_g_r["monto"].astype(float).sum()) if not df_g_r.empty and "monto" in df_g_r else 0.0

    st.subheader("Balance del Período")
    r1, r2, r3 = st.columns(3)
    r1.metric("Ingresos (+)", f"C$ {total_ingresos:.2f}")
    r2.metric("Gastos (-)", f"C$ {total_gastos:.2f}")
    r3.metric("Ganancia Real (=)", f"C$ {total_ingresos - total_gastos:.2f}")