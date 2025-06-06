# Simulador PowerHub Escolar - Interfaz Streamlit
# Proyecto: Electrificación Solar de Escuelas Rurales - SKLATAM + Sun King

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# === CONFIGURACIÓN DE USUARIO ===
st.set_page_config(page_title="Simulador Solar Escolar", layout="wide")
st.title("\U0001F31E Simulador PowerHub Escolar")
st.markdown("""
Este simulador permite analizar el desempeño de sistemas solares Sun King para escuelas rurales
según su ubicación solar (zona), configuración de paneles/baterías y condiciones climáticas.
""")

# === PARÁMETROS DE ENTRADA ===
col1, col2, col3 = st.columns(3)

zona = col1.selectbox("Zona Solar", ["zona_1", "zona_2", "zona_3"], index=2)
sistema = col2.selectbox("Sistema Solar", ["Sistema_1", "Sistema_2"])
usar_peor_mes = col3.checkbox("Simular Peor Mes (Nov-Dic)?", value=True)

factor_tormenta = st.slider("Factor de Tormenta", min_value=0.1, max_value=1.0, value=1.0, step=0.05)
simulation_hours = st.slider("Duración de la Simulación (horas)", 24, 240, 120, step=24)
year = st.number_input("Año de Operación (para degradación)", min_value=0, max_value=10, value=1)

# === CURVAS DE MARZO POR ZONA ===
curvas_marzo = {
    "zona_1": {"6-7": 0.051, "7-8": 0.468, "8-9": 1.012, "9-10": 1.449, "10-11": 1.757, "11-12": 1.861,
               "12-13": 1.885, "13-14": 1.700, "14-15": 1.311, "15-16": 0.981, "16-17": 0.639, "17-18": 0.269, "18-19": 0.042},
    "zona_2": {"6-7": 0.061, "7-8": 0.554, "8-9": 1.200, "9-10": 1.717, "10-11": 2.083, "11-12": 2.204,
               "12-13": 2.233, "13-14": 2.013, "14-15": 1.552, "15-16": 1.161, "16-17": 0.756, "17-18": 0.318, "18-19": 0.050},
    "zona_3": {"6-7": 0.075, "7-8": 0.688, "8-9": 1.487, "9-10": 2.128, "10-11": 2.577, "11-12": 2.728,
               "12-13": 2.765, "13-14": 2.493, "14-15": 1.918, "15-16": 1.435, "16-17": 0.934, "17-18": 0.393, "18-19": 0.062}
}

pvout_marzo = {"zona_1": 99.09, "zona_2": 116.57, "zona_3": 146.28}
factor_peor_mes = {"zona_1": 0.773, "zona_2": 0.799, "zona_3": 0.712}

# === CONFIGURACIÓN DE SISTEMAS ===
sistemas = {
    "Sistema_1": {"solar_panels": 9, "batteries": 2},
    "Sistema_2": {"solar_panels": 12, "batteries": 3}
}

# === PARÁMETROS FIJOS ===
panel_power_W = 450
battery_unit_kWh = 2.56
inverter_limit_kW = 3.3
comm_power_W = 162.5
laptops_power_W = 700

solar_kWp = (sistemas[sistema]["solar_panels"] * panel_power_W) / 1000
battery_total_kWh = sistemas[sistema]["batteries"] * battery_unit_kWh

# === ESCALADO CURVA HORARIA ===
base_gen = curvas_marzo[zona]
total_relativo = sum(base_gen.values())
pvout_base = pvout_marzo[zona] * (factor_peor_mes[zona] if usar_peor_mes else 1)
factor_escala = pvout_base / 30

curva_horaria_diaria = {h: (v / total_relativo) * factor_escala for h, v in base_gen.items()}
full_day = {f"{h}-{h+1}": 0.0 for h in range(24)}
full_day.update(curva_horaria_diaria)
day_template = dict(sorted(full_day.items(), key=lambda x: int(x[0].split("-")[0])))

# === GENERACIÓN HORARIA SIMULADA ===
storm_start_hour = 24
solar_generation_input = {}
for d in range(simulation_hours // 24):
    for h in range(24):
        idx = d * 24 + h
        label = f"{idx}-{idx + 1}"
        hour_label = f"{h}-{h+1}"
        value = day_template.get(hour_label, 0.0)
        if idx >= storm_start_hour:
            value *= factor_tormenta
        solar_generation_input[label] = value

def generate_solar_curve(kWp, degradation_years=0):
    deg_factor = (1 - 0.005) ** degradation_years
    return {hour: min(round(val * kWp * deg_factor, 3), inverter_limit_kW)
            for hour, val in solar_generation_input.items()}

def simulate_day(kWp, battery_kWh):
    generation = generate_solar_curve(kWp, degradation_years=year)
    usable_batt = battery_kWh * 0.95 * (1 - 0.30) * ((1 - 0.015) ** year)
    battery_state = usable_batt
    battery_curve = {}
    consumption = {}
    failure_hour = None

    for t, gen_kWh in generation.items():
        h = int(t.split("-")[0]) % 24
        cons = (comm_power_W + (laptops_power_W if 8 <= h < 16 else 0)) / 1000
        net = gen_kWh - cons
        battery_state = max(0, min(battery_state + net, usable_batt))
        battery_curve[t] = round(battery_state, 2)
        consumption[t] = cons

        if failure_hour is None and int(t.split("-")[0]) >= storm_start_hour and battery_state < cons:
            failure_hour = int(t.split("-")[0])

    horas_post = failure_hour - storm_start_hour if failure_hour else simulation_hours - storm_start_hour
    return generation, consumption, battery_curve, usable_batt, horas_post, failure_hour

# === SIMULACIÓN ===
gen, cons, batt, usable, running_hours, failure_hour = simulate_day(solar_kWp, battery_total_kWh)

# === GRÁFICO ===
st.subheader("\U0001F4CA Resultados de la Simulación")
df = pd.DataFrame({
    "Hora": list(gen.keys()),
    "Generación Solar (kWh)": list(gen.values()),
    "Consumo (kWh)": [cons[k] for k in gen],
    "Batería (kWh)": list(batt.values())
})

fig, ax = plt.subplots(figsize=(16, 5))
ax.plot(df["Hora"], df["Generación Solar (kWh)"], label="Generación Solar", marker='o')
ax.plot(df["Hora"], df["Consumo (kWh)"], label="Consumo", marker='o')
ax.plot(df["Hora"], df["Batería (kWh)"], label="Estado Batería", marker='o')
if failure_hour:
    ax.axvline(x=failure_hour, color='red', linestyle='--', label=f"Falla a la hora {failure_hour}")
ax.set_xticks(range(0, len(df), 3))
ax.set_xticklabels([df['Hora'][i] for i in range(0, len(df), 3)], rotation=45, fontsize=8)
ax.set_title("Simulación Solar por Hora")
ax.set_ylabel("Energía (kWh)")
ax.grid(True)
ax.legend()
st.pyplot(fig)

# === RESUMEN ===
st.markdown("""
**Resumen del Sistema**
- Zona Solar: **{zona.upper()}**
- Sistema: **{sistema}**
- Capacidad Solar: **{solar_kWp:.2f} kWp**
- Capacidad Batería Total: **{battery_total_kWh:.2f} kWh**
- Batería Usable: **{usable:.2f} kWh**
- Falla tras tormenta: **{failure_hour if failure_hour else 'No hay falla'}**
- Horas operativas post-tormenta: **{running_hours}**
""")
