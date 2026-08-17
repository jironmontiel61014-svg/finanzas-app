import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# Configuración de página
st.set_page_config(page_title="Control de Finanzas - Lauren", page_icon="💰", layout="wide")

# Conexión a Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

st.title("💼 Sistema de Control Financiero")

# --- FUNCIONES DE DIÁLOGO PARA EDICIÓN ---
@st.dialog("✏️ Editar Pago Fijo")
def editar_pago_fijo_dialog(pago_fijo_id, historial_id, nombre_actual, monto_actual):
    st.write(f"Modificar datos de **{nombre_actual}**:")
    with st.form("form_edit_dialog"):
        nuevo_nom = st.text_input("Nombre:", value=nombre_actual)
        nuevo_monto = st.number_input("Monto este mes ($):", value=float(monto_actual), step=5.0)
        if st.form_submit_button("Guardar Cambios"):
            nom_limpio = nuevo_nom.replace("*", "").strip()
            # Actualizar catálogo general
            supabase.table("pagos_fijos").update({"nombre": nom_limpio}).eq("id", pago_fijo_id).execute()
            # Actualizar monto específico del mes
            supabase.table("historial_pagos").update({"monto": nuevo_monto}).eq("id", historial_id).execute()
            st.success("Actualizado correctamente")
            st.rerun()

# --- NAVEGACIÓN POR PESTAÑAS ---
tab_control, tab_alarmas, tab_deudas_fijas, tab_config = st.tabs([
    "📊 Control Mensual", 
    "🚨 Alarmas y Prioridades",
    "💳 Deudas Fijas", 
    "⚙️ Configurar Pagos Fijos"
])

meses = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]

# ==========================================
# PESTAÑA 1: CONTROL MENSUAL DE PAGOS
# ==========================================
with tab_control:
    col_mes, col_anio = st.columns(2)
    with col_mes:
        mes_seleccionado = st.selectbox("Selecciona el Mes:", meses, index=7) # Agosto por defecto
    with col_anio:
        anio_seleccionado = st.selectbox("Selecciona el Año:", [2026, 2027], index=0)

    st.divider()

    # Carga de datos
    res_fijos = supabase.table("pagos_fijos").select("*").execute()
    df_fijos = pd.DataFrame(res_fijos.data)

    res_hist = supabase.table("historial_pagos").select("*").eq("mes", mes_seleccionado).eq("anio", anio_seleccionado).execute()
    df_historial = pd.DataFrame(res_hist.data)

    res_otros = supabase.table("otros_pagos").select("*").eq("mes", mes_seleccionado).eq("anio", anio_seleccionado).execute()
    df_otros = pd.DataFrame(res_otros.data)

    # Auto-crear registros del mes si no existen
    if df_historial.empty and not df_fijos.empty:
        nuevos_registros = [
            {"pago_fijo_id": row["id"], "mes": mes_seleccionado, "anio": anio_seleccionado, "monto": row["monto_defecto"], "estado": "PENDIENTE"}
            for _, row in df_fijos.iterrows()
        ]
        supabase.table("historial_pagos").insert(nuevos_registros).execute()
        res_hist = supabase.table("historial_pagos").select("*").eq("mes", mes_seleccionado).eq("anio", anio_seleccionado).execute()
        df_historial = pd.DataFrame(res_hist.data)

    df_completo = pd.merge(df_fijos, df_historial, left_on="id", right_on="pago_fijo_id", suffixes=("_base", "_mes")) if not df_historial.empty and not df_fijos.empty else pd.DataFrame()

    # Saldo acumulado de meses anteriores
    idx_mes_actual = meses.index(mes_seleccionado)
    meses_anteriores = meses[:idx_mes_actual]
    pendiente_meses_anteriores = 0.0

    if meses_anteriores:
        res_h_ant = supabase.table("historial_pagos").select("monto").in_("mes", meses_anteriores).eq("anio", anio_seleccionado).eq("estado", "PENDIENTE").execute()
        if res_h_ant.data:
            pendiente_meses_anteriores += sum([item["monto"] for item in res_h_ant.data])

        res_o_ant = supabase.table("otros_pagos").select("monto").in_("mes", meses_anteriores).eq("anio", anio_seleccionado).eq("estado", "PENDIENTE").execute()
        if res_o_ant.data:
            pendiente_meses_anteriores += sum([item["monto"] for item in res_o_ant.data])

    # Cálculos del mes actual
    monto_fijo_pen = df_completo[df_completo["estado"] == "PENDIENTE"]["monto"].sum() if not df_completo.empty else 0.0
    monto_otros_pen = df_otros[df_otros["estado"] == "PENDIENTE"]["monto"].sum() if not df_otros.empty else 0.0
    monto_fijo_pag = df_completo[df_completo["estado"] == "PAGADO"]["monto"].sum() if not df_completo.empty else 0.0
    monto_otros_pag = df_otros[df_otros["estado"] == "PAGADO"]["monto"].sum() if not df_otros.empty else 0.0

    pendiente_mes_actual = monto_fijo_pen + monto_otros_pen
    total_pagado_mes = monto_fijo_pag + monto_otros_pag
    total_global_conseguir = pendiente_meses_anteriores + pendiente_mes_actual

    # TARJETA FORMATO VISUAL DE RESUMEN
    if pendiente_meses_anteriores > 0:
        st.markdown(
            f"""
            <div style="background-color: #FFF3CD; border-left: 6px solid #FFC107; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                <h4 style="margin:0; color: #856404;">📌 Resumen Personal de Pagos Acumulados</h4>
                <p style="margin: 10px 0 0 0; font-size: 16px; color: #856404; line-height: 1.5;">
                    Debes la cantidad de <strong>${pendiente_meses_anteriores:,.2f}</strong> de los meses anteriores, sumado esa cantidad con lo proyectado de este mes ({mes_seleccionado}) más otros préstamos se hace un total de <strong>${total_global_conseguir:,.2f}</strong>.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div style="background-color: #D4EDDA; border-left: 6px solid #28A745; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                <h4 style="margin:0; color: #155724;">👏 ¡Al Día con Meses Anteriores!</h4>
                <p style="margin: 10px 0 0 0; font-size: 16px; color: #155724; line-height: 1.5;">
                    No tienes deudas pendientes de meses anteriores. Para el mes de <strong>{mes_seleccionado}</strong> el total proyectado a conseguir es de <strong>${total_global_conseguir:,.2f}</strong>.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

    # TARJETAS DE MÉTRICAS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🚨 PAGOS PENDIENTES DE MESES ANTERIORES", f"${pendiente_meses_anteriores:,.2f}")
    c2.metric(f"📅 PENDIENTE {mes_seleccionado}", f"${pendiente_mes_actual:,.2f}")
    c3.metric(f"🔥 TOTAL A CONSEGUIR A FINAL DE {mes_seleccionado}", f"${total_global_conseguir:,.2f}")
    c4.metric(f"✅ PAGADO ESTE MES DE {mes_seleccionado}", f"${total_pagado_mes:,.2f}")

    st.divider()

    # LISTADO PAGOS FIJOS
    st.subheader(f"1. Pagos Fijos Mensuales - {mes_seleccionado}")

    # Formulario para agregar un nuevo Pago Fijo directamente en Control Mensual
    with st.expander("➕ Agregar nuevo pago fijo"):
        with st.form("form_nuevo_pago_fijo_ctrl"):
            nuevo_nom_fijo = st.text_input("Nombre del Pago Fijo (Ej: Internet, Seguro):")
            nuevo_monto_fijo = st.number_input("Monto por defecto ($):", min_value=0.0, step=5.0)
            if st.form_submit_button("Guardar Pago Fijo") and nuevo_nom_fijo:
                nom_limpio = nuevo_nom_fijo.replace("*", "").strip()
                res_ins = supabase.table("pagos_fijos").insert({
                    "nombre": nom_limpio,
                    "monto_defecto": nuevo_monto_fijo
                }).execute()
                
                if res_ins.data:
                    pago_fijo_creado_id = res_ins.data[0]["id"]
                    supabase.table("historial_pagos").insert({
                        "pago_fijo_id": pago_fijo_creado_id,
                        "mes": mes_seleccionado,
                        "anio": anio_seleccionado,
                        "monto": nuevo_monto_fijo,
                        "estado": "PENDIENTE"
                    }).execute()

                st.success(f"Pago fijo '{nom_limpio}' agregado correctamente.")
                st.rerun()

    if not df_completo.empty:
        # Estilos CSS para centrado vertical y cajas de estado uniformes
        st.markdown(
            """
            <style>
            div[data-testid="stColumn"] {
                display: flex;
                align-items: center;
            }
            .badge-pagado {
                background-color: #D4EDDA;
                color: #155724;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 14px;
                display: inline-block;
                width: 100%;
                text-align: center;
            }
            .badge-pendiente {
                background-color: #F8D7DA;
                color: #721C24;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 14px;
                display: inline-block;
                width: 100%;
                text-align: center;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        for idx, row in df_completo.iterrows():
            col_nom, col_monto, col_estado, col_btn, col_edit, col_del = st.columns([3, 2, 2, 2, 1, 1])
            
            # Limpiar nombre para eliminar asteriscos residuales guardados previamente
            nombre_limpio = str(row['nombre']).replace("*", "").strip()
            
            col_nom.write(f"**{nombre_limpio}**")
            col_monto.write(f"${row['monto']:.2f}")

            if row["estado"] == "PAGADO":
                col_estado.markdown('<div class="badge-pagado">PAGADO</div>', unsafe_allow_html=True)
                if col_btn.button("Marcar Pendiente", key=f"fijo_p_{row['id_mes']}"):
                    supabase.table("historial_pagos").update({"estado": "PENDIENTE"}).eq("id", row["id_mes"]).execute()
                    st.rerun()
            else:
                col_estado.markdown('<div class="badge-pendiente">PENDIENTE</div>', unsafe_allow_html=True)
                if col_btn.button("Marcar Pagado", key=f"fijo_c_{row['id_mes']}"):
                    supabase.table("historial_pagos").update({"estado": "PAGADO"}).eq("id", row["id_mes"]).execute()
                    st.rerun()

            # Botón de edición que abre la ventana emergente modal
            if col_edit.button("✏️", key=f"btn_edit_dialog_{row['id_mes']}", help="Editar este pago"):
                editar_pago_fijo_dialog(row["id_base"], row["id_mes"], nombre_limpio, row["monto"])

            # Opción para eliminar el pago fijo
            if col_del.button("🗑️", key=f"del_pf_ctrl_{row['id_base']}", help="Eliminar este pago fijo"):
                supabase.table("historial_pagos").delete().eq("pago_fijo_id", row["id_base"]).execute()
                supabase.table("pagos_fijos").delete().eq("id", row["id_base"]).execute()
                st.success("Pago fijo eliminado")
                st.rerun()

    st.divider()

    # OTROS PAGOS (EMERGENTES)
    st.subheader(f"2. OTROS PAGOS (Préstamos / Gastos Emergentes) - {mes_seleccionado}")
    with st.expander("➕ Agregar nuevo pago emergente"):
        with st.form("form_nuevo_otro"):
            desc = st.text_input("Descripción del pago:")
            monto_i = st.number_input("Monto en $:", min_value=0.0, step=1.0)
            if st.form_submit_button("Guardar Pago") and desc and monto_i > 0:
                desc_limpia = desc.replace("*", "").strip()
                supabase.table("otros_pagos").insert({"descripcion": desc_limpia, "monto": monto_i, "mes": mes_seleccionado, "anio": anio_seleccionado, "estado": "PENDIENTE"}).execute()
                st.success("Guardado")
                st.rerun()

    if not df_otros.empty:
        for idx, row in df_otros.iterrows():
            col_nom, col_monto, col_estado, col_btn, col_del = st.columns([3, 2, 2, 2, 1])
            desc_limpia = str(row['descripcion']).replace("*", "").strip()
            col_nom.write(f"**{desc_limpia}**")
            col_monto.write(f"${row['monto']:.2f}")
            
            if row["estado"] == "PAGADO":
                col_estado.markdown('<div class="badge-pagado">PAGADO</div>', unsafe_allow_html=True)
                if col_btn.button("Marcar Pendiente", key=f"otro_p_{row['id']}"):
                    supabase.table("otros_pagos").update({"estado": "PENDIENTE"}).eq("id", row["id"]).execute()
                    st.rerun()
            else:
                col_estado.markdown('<div class="badge-pendiente">PENDIENTE</div>', unsafe_allow_html=True)
                if col_btn.button("Marcar Pagado", key=f"otro_c_{row['id']}"):
                    supabase.table("otros_pagos").update({"estado": "PAGADO"}).eq("id", row["id"]).execute()
                    st.rerun()
            
            if col_del.button("🗑️", key=f"del_otro_{row['id']}", help="Eliminar este pago"):
                supabase.table("otros_pagos").delete().eq("id", row["id"]).execute()
                st.rerun()


# ==========================================
# PESTAÑA 2: ALARMAS Y PRIORIDADES DE PAGO
# ==========================================
with tab_alarmas:
    st.header("🚨 Alarmas y Prioridades (Atrasos de Meses Anteriores)")
    st.write(f"Muestra **únicamente** los pagos que quedaron vencidos de meses anteriores a **{mes_seleccionado} {anio_seleccionado}**.")

    meses_vencidos = meses[:idx_mes_actual]

    if meses_vencidos:
        res_h_alarm = supabase.table("historial_pagos").select("*").in_("mes", meses_vencidos).eq("anio", anio_seleccionado).eq("estado", "PENDIENTE").execute()
        df_h_alarm = pd.DataFrame(res_h_alarm.data)

        res_o_alarm = supabase.table("otros_pagos").select("*").in_("mes", meses_vencidos).eq("anio", anio_seleccionado).eq("estado", "PENDIENTE").execute()
        df_o_alarm = pd.DataFrame(res_o_alarm.data)

        lista_resumen = []

        if not df_h_alarm.empty and not df_fijos.empty:
            df_fijos_alarm = pd.merge(df_fijos, df_h_alarm, left_on="id", right_on="pago_fijo_id")
            
            for nombre_pago, group in df_fijos_alarm.groupby("nombre"):
                cant_cuotas = len(group)
                meses_list = list(group["mes"])
                total_monto = group["monto"].sum()
                
                meses_list.sort(key=lambda m: meses.index(m))
                
                nombre_clean = str(nombre_pago).replace("*", "").strip()
                lista_resumen.append({
                    "Concepto / Deuda": nombre_clean,
                    "Tipo": "Pago Fijo",
                    "Cuotas Pendientes": cant_cuotas,
                    "Meses Afectados": ", ".join(meses_list),
                    "Monto Acumulado ($)": total_monto
                })

        if not df_o_alarm.empty:
            for desc_pago, group in df_o_alarm.groupby("descripcion"):
                cant_cuotas = len(group)
                meses_list = list(group["mes"])
                total_monto = group["monto"].sum()
                
                meses_list.sort(key=lambda m: meses.index(m))
                
                desc_clean = str(desc_pago).replace("*", "").strip()
                lista_resumen.append({
                    "Concepto / Deuda": desc_clean,
                    "Tipo": "Préstamo / Emergente",
                    "Cuotas Pendientes": cant_cuotas,
                    "Meses Afectados": ", ".join(meses_list),
                    "Monto Acumulado ($)": total_monto
                })

        if lista_resumen:
            df_resumen_alarmas = pd.DataFrame(lista_resumen)
            
            total_deudas_pendientes = len(df_resumen_alarmas)
            monto_total_prioridad = df_resumen_alarmas["Monto Acumulado ($)"].sum()
            
            st.markdown(
                f"""
                <div style="background-color: #FFEBEE; border-left: 6px solid #D32F2F; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
                    <h4 style="margin:0; color: #C62828;">⚠️ ATENCIÓN: Tienes {total_deudas_pendientes} compromiso(s) con cuotas atrasadas</h4>
                    <p style="margin: 5px 0 0 0; font-size: 16px; color: #B71C1C;">
                        El monto vencido acumulado de meses anteriores a <strong>{mes_seleccionado}</strong> es de <strong>${monto_total_prioridad:,.2f}</strong>.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.subheader("📋 Tabla de Prioridades de Pago")
            
            st.dataframe(
                df_resumen_alarmas,
                column_config={
                    "Concepto / Deuda": st.column_config.TextColumn("Concepto / Deuda"),
                    "Tipo": st.column_config.TextColumn("Tipo de Cargo"),
                    "Cuotas Pendientes": st.column_config.NumberColumn("Cuotas Atrasadas", format="%d cuota(s)"),
                    "Meses Afectados": st.column_config.TextColumn("Meses Pendientes"),
                    "Monto Acumulado ($)": st.column_config.NumberColumn("Monto Atrasado", format="$%.2f")
                },
                hide_index=True,
                use_container_width=True
            )

            st.divider()
            st.subheader("📌 Desglose Individual de Alarmas")

            for item in lista_resumen:
                st.markdown(
                    f"""
                    <div style="background-color: #FFFFFF; border: 1px solid #E0E0E0; border-top: 4px solid #D32F2F; border-radius: 8px; padding: 15px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h4 style="margin: 0; color: #212121;">{item['Concepto / Deuda']} <span style="font-size: 12px; color: #757575;">({item['Tipo']})</span></h4>
                            <span style="background-color: #FFCDD2; color: #B71C1C; font-weight: bold; padding: 4px 10px; border-radius: 12px; font-size: 13px;">
                                {item['Cuotas Pendientes']} cuota(s) atrasada(s)
                            </span>
                        </div>
                        <p style="margin: 10px 0 5px 0; font-size: 14px; color: #424242;">
                            <strong>Meses acumulados:</strong> <span style="color: #D32F2F; font-weight: bold;">{item['Meses Afectados']}</span>
                        </p>
                        <p style="margin: 0; font-size: 16px; color: #212121;">
                            <strong>Monto Total Vencido:</strong> <span style="font-size: 18px; color: #D32F2F; font-weight: bold;">${item['Monto Acumulado ($)']:,.2f}</span>
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.success("🎉 ¡Excelente! No tienes ninguna cuota atrasada de meses anteriores.")
    else:
        st.info("Enero es el primer mes del año, no existen meses anteriores acumulados.")


# ==========================================
# PESTAÑA 3: DEUDAS FIJAS
# ==========================================
with tab_deudas_fijas:
    st.header("📋 Registro de Deudas Fijas")
    st.write("Catálogo detallado de acreedores, compromisos financieros y plazos de pago.")

    with st.expander("➕ Registrar Nueva Deuda Fija"):
        with st.form("form_deuda_fija"):
            c_prov, c_tipo = st.columns(2)
            proveedor = c_prov.text_input("Proveedor / Acreedor (Ej: Banco BAC, Financiera):")
            tipo_deuda = c_tipo.selectbox("Tipo de Deuda:", ["Tarjeta de Crédito", "Préstamo Bancario", "Préstamo Personal", "Servicio Fijo", "Otro"])
            
            c_nom, c_cuota = st.columns(2)
            nombre_deuda = c_nom.text_input("Nombre / Descripción de la Deuda:")
            cuota_m = c_cuota.number_input("Cuota Mensual ($):", min_value=0.0, step=10.0)
            
            c_fecha_p, c_fecha_f, c_monto_r = st.columns(3)
            fecha_pago = c_fecha_p.selectbox("Fecha de Pago:", ["15 de cada mes", "30 de cada mes"])
            fecha_fin = c_fecha_f.date_input("Fecha Fin de Deuda:")
            monto_real = c_monto_r.number_input("Monto Real Adeudado ($):", min_value=0.0, step=50.0)

            if st.form_submit_button("Guardar Deuda Fija") and proveedor and nombre_deuda:
                nom_deuda_clean = nombre_deuda.replace("*", "").strip()
                supabase.table("deudas_fijas").insert({
                    "proveedor": proveedor,
                    "tipo_deuda": tipo_deuda,
                    "nombre": nom_deuda_clean,
                    "cuota_mensual": cuota_m,
                    "fecha_pago": fecha_pago,
                    "fecha_fin": str(fecha_fin),
                    "monto_real_adeudado": monto_real
                }).execute()
                st.success(f"Deuda '{nom_deuda_clean}' registrada con éxito.")
                st.rerun()

    res_deudas = supabase.table("deudas_fijas").select("*").order("created_at", desc=False).execute()
    df_df = pd.DataFrame(res_deudas.data)

    if not df_df.empty:
        total_monto_real = df_df["monto_real_adeudado"].sum()
        total_cuotas = df_df["cuota_mensual"].sum()
        
        col_t1, col_t2 = st.columns(2)
        col_t1.markdown(
            f"""
            <div style="background-color: #E3F2FD; border: 2px solid #2196F3; padding: 15px; border-radius: 10px; text-align: center;">
                <h5 style="color: #0D47A1; margin: 0;">💰 TOTAL MONTO REAL ADEUDADO</h5>
                <h2 style="color: #1565C0; margin: 5px 0 0 0;">${total_monto_real:,.2f}</h2>
            </div>
            """,
            unsafe_allow_html=True
        )
        col_t2.markdown(
            f"""
            <div style="background-color: #F3E5F5; border: 2px solid #9C27B0; padding: 15px; border-radius: 10px; text-align: center;">
                <h5 style="color: #4A148C; margin: 0;">🗓️ SUMA TOTAL DE CUOTAS MENSUALES</h5>
                <h2 style="color: #7B1FA2; margin: 5px 0 0 0;">${total_cuotas:,.2f}</h2>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.subheader("Detalle de Deudas Registradas")
        
        for idx, row in df_df.iterrows():
            with st.container():
                d_nombre_clean = str(row['nombre']).replace("*", "").strip()
                st.markdown(f"### {d_nombre_clean} — *{row['proveedor']}*")
                col_d1, col_d2, col_d3, col_d4 = st.columns([2, 2, 2, 2])
                
                col_d1.write(f"**Tipo:** {row['tipo_deuda']}")
                col_d2.write(f"**Cuota Mensual:** ${row['cuota_mensual']:,.2f}")
                col_d3.write(f"**Día de Pago:** {row['fecha_pago']}")
                col_d4.write(f"**Monto Real:** ${row['monto_real_adeudado']:,.2f}")
                
                col_b1, col_b2 = st.columns([1, 1])
                with col_b1:
                    with st.expander("✏️ Editar Deuda"):
                        with st.form(f"form_edit_deuda_{row['id']}"):
                            e_prov = st.text_input("Proveedor:", value=row['proveedor'])
                            e_nom = st.text_input("Nombre Deuda:", value=d_nombre_clean)
                            e_tipo = st.selectbox("Tipo:", ["Tarjeta de Crédito", "Préstamo Bancario", "Préstamo Personal", "Servicio Fijo", "Otro"], index=0)
                            e_cuota = st.number_input("Cuota Mensual ($):", value=float(row['cuota_mensual']), step=10.0)
                            e_fecha_p = st.selectbox("Fecha Pago:", ["15 de cada mes", "30 de cada mes"], index=0 if row['fecha_pago']=="15 de cada mes" else 1)
                            e_monto_r = st.number_input("Monto Real Adeudado ($):", value=float(row['monto_real_adeudado']), step=50.0)
                            
                            if st.form_submit_button("Guardar Cambios"):
                                e_nom_clean = e_nom.replace("*", "").strip()
                                supabase.table("deudas_fijas").update({
                                    "proveedor": e_prov,
                                    "nombre": e_nom_clean,
                                    "tipo_deuda": e_tipo,
                                    "cuota_mensual": e_cuota,
                                    "fecha_pago": e_fecha_p,
                                    "monto_real_adeudado": e_monto_r
                                }).eq("id", row['id']).execute()
                                st.success("Deuda actualizada correctamente.")
                                st.rerun()

                with col_b2:
                    if st.button("🗑️ Eliminar Deuda", key=f"del_df_{row['id']}"):
                        supabase.table("deudas_fijas").delete().eq("id", row["id"]).execute()
                        st.success("Deuda eliminada")
                        st.rerun()

                st.caption(f"Fecha Fin: {row['fecha_fin']}")
                st.divider()
    else:
        st.info("No hay deudas fijas registradas. Agrega una con el formulario superior.")


# ==========================================
# PESTAÑA 4: CONFIGURAR PAGOS FIJOS
# ==========================================
with tab_config:
    st.header("⚙️ Gestión del Catálogo de Pagos Fijos Mensuales")
    st.write("Agrega, modifica o elimina compromisos del listado recurrente mensual.")

    with st.expander("➕ Agregar Nueva Categoría al Catálogo"):
        with st.form("form_nueva_cat_fija"):
            nom_cat = st.text_input("Nombre del Pago Fijo (Ej: Casa, Agua, Tarjeta BAC):")
            monto_cat = st.number_input("Monto por Defecto ($):", min_value=0.0, step=10.0)
            if st.form_submit_button("Añadir al Catálogo") and nom_cat:
                cat_clean = nom_cat.replace("*", "").strip()
                supabase.table("pagos_fijos").insert({
                    "nombre": cat_clean,
                    "monto_defecto": monto_cat
                }).execute()
                st.success(f"Categoría '{cat_clean}' añadida correctamente.")
                st.rerun()

    st.subheader("Catálogo Actual")
    if not df_fijos.empty:
        for idx, row in df_fijos.iterrows():
            col_c1, col_c2, col_c3, col_c4 = st.columns([3, 2, 2, 2])
            cat_nom_clean = str(row['nombre']).replace("*", "").strip()
            col_c1.write(f"**{cat_nom_clean}**")
            col_c2.write(f"Monto por defecto: **${row['monto_defecto']:.2f}**")
            
            with col_c3:
                with st.expander("✏️ Modificar"):
                    with st.form(f"form_mod_pf_{row['id']}"):
                        mod_nombre = st.text_input("Nombre:", value=cat_nom_clean)
                        mod_monto = st.number_input("Monto Defecto ($):", value=float(row['monto_defecto']), step=5.0)
                        if st.form_submit_button("Guardar"):
                            mod_clean = mod_nombre.replace("*", "").strip()
                            supabase.table("pagos_fijos").update({
                                "nombre": mod_clean,
                                "monto_defecto": mod_monto
                            }).eq("id", row['id']).execute()
                            st.success("Modificado")
                            st.rerun()

            with col_c4:
                if st.button("🗑️ Eliminar", key=f"del_pf_{row['id']}"):
                    supabase.table("historial_pagos").delete().eq("pago_fijo_id", row["id"]).execute()
                    supabase.table("pagos_fijos").delete().eq("id", row["id"]).execute()
                    st.success(f"Categoría '{cat_nom_clean}' eliminada.")
                    st.rerun()
    else:
        st.info("El catálogo de pagos fijos está vacío.")