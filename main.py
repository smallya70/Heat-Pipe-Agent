import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import csv
import io


st.set_page_config(page_title="Industrial Digital Twin", layout="wide")
st.sidebar.header("🛠️ System Configuration")
st.markdown(
    """
<style>
.property-badge {
    display: inline-block;
    padding: 0.35rem 0.6rem;
    border-radius: 999px;
    font-size: 0.86rem;
    font-weight: 600;
    margin-top: 0.2rem;
}
.property-badge.low {
    background: #e6f6ea;
    color: #17663a;
}
.property-badge.medium {
    background: #fff4dd;
    color: #8a5a00;
}
.property-badge.high {
    background: #fde8e8;
    color: #a61b1b;
}
.property-badge.disabled {
    background: #eceff3;
    color: #495057;
}
</style>
""",
    unsafe_allow_html=True,
)


def reset_app_to_defaults():
    st.session_state.f_input = 0.002
    st.session_state.d_input = 0.05
    st.session_state.l_input = 10.0
    st.session_state.temp_input = 25
    st.session_state.fluid_preset = "Water"
    st.session_state.manual_density = 997.0
    st.session_state.manual_viscosity = 0.000890
    st.session_state.custom_base_density = 900.0
    st.session_state.custom_base_viscosity = 0.050000
    st.session_state.custom_base_cp = 2200.0
    st.session_state.custom_base_k = 0.145
    st.session_state.property_source = ""
    st.session_state.enable_density_correction = True
    st.session_state.measured_dp = float(st.session_state.current_dp_for_sync)
    st.session_state.alert_baseline_dp = float(st.session_state.current_dp_for_sync)
    st.session_state.alert_threshold_pct = 1.0


def reset_fluid_properties():
    st.session_state.fluid_preset = "Water"
    st.session_state.temp_input = 25
    st.session_state.manual_density = 997.0
    st.session_state.manual_viscosity = 0.000890
    st.session_state.custom_base_density = 900.0
    st.session_state.custom_base_viscosity = 0.050000
    st.session_state.custom_base_cp = 2200.0
    st.session_state.custom_base_k = 0.145
    st.session_state.property_source = ""
    st.session_state.enable_density_correction = True


def sync_sensor_to_model():
    st.session_state.measured_dp = float(st.session_state.current_dp_for_sync)


def sync_alert_baseline_to_model():
    st.session_state.alert_baseline_dp = float(st.session_state.current_dp_for_sync)


st.sidebar.button("Reset To Default", on_click=reset_app_to_defaults)
st.sidebar.button("Reset Fluid Properties", on_click=reset_fluid_properties)
st.sidebar.markdown("---")
st.sidebar.subheader("Process Inputs")
f_input = st.sidebar.slider("Flow Rate (m³/s)", 0.0001, 0.01, 0.002, format="%.4f", key="f_input")
d_input = st.sidebar.slider("Pipe Diameter (m)", 0.01, 0.15, 0.05, key="d_input")
l_input = st.sidebar.slider("Pipe Length (m)", 1.0, 500.0, 10.0, key="l_input")
temp_input = st.sidebar.slider("Fluid Temp (°C)", 10, 100, 25, key="temp_input")


temp_ambient = 20.0
baseline_temp = 25.0
fluid_presets = {
    "Custom Manual": {"mu": 0.050000, "rho": 900.0, "cp": 2200.0, "k": 0.145},
    "Water": {"mu": 0.000890, "rho": 997.0, "cp": 4187.0, "k": 0.598},
    "Light Oil": {"mu": 0.035, "rho": 870.0, "cp": 2100.0, "k": 0.145, "mu_coeff": 0.028, "rho_coeff": 0.00070, "cp_slope": 2.5, "k_slope": -0.00012},
    "Heavy Oil": {"mu": 0.250, "rho": 950.0, "cp": 1900.0, "k": 0.130, "mu_coeff": 0.035, "rho_coeff": 0.00065, "cp_slope": 2.0, "k_slope": -0.00015},
    "Glycerin": {"mu": 1.200, "rho": 1260.0, "cp": 2400.0, "k": 0.285, "mu_coeff": 0.045, "rho_coeff": 0.00055, "cp_slope": 1.8, "k_slope": -0.00010},
}


def get_fluid_properties(temperature_c, preset_name):
    if preset_name == "Custom Manual":
        rho_val = st.session_state.custom_base_density
        cp_val = st.session_state.custom_base_cp
        k_val = st.session_state.custom_base_k
        mu_val = st.session_state.custom_base_viscosity
        return rho_val, cp_val, k_val, mu_val

    if preset_name == "Water":
        rho_val = 1000 * (1 - (temperature_c + 288.94) / (508929 * (temperature_c + 68.12)) * (temperature_c - 3.98) ** 2)
        cp_val = 4176.2 + 0.45 * temperature_c
        k_val = 0.561 + 0.0018 * temperature_c - 0.000003 * temperature_c**2
        mu_val = 0.00179 / (1 + 0.03368 * temperature_c + 0.00022 * temperature_c**2)
        return rho_val, cp_val, k_val, mu_val

    preset = fluid_presets[preset_name]
    delta_t = temperature_c - baseline_temp
    rho_val = max(1.0, preset["rho"] * (1 - preset["rho_coeff"] * delta_t))
    cp_val = max(500.0, preset["cp"] + preset["cp_slope"] * delta_t)
    k_val = max(0.01, preset["k"] + preset["k_slope"] * delta_t)
    mu_val = max(0.0001, preset["mu"] * np.exp(-preset["mu_coeff"] * delta_t))
    return rho_val, cp_val, k_val, mu_val


def apply_density_correction(base_cp, base_k, active_density, reference_density):
    if reference_density <= 0:
        return base_cp, base_k
    density_shift = (active_density - reference_density) / reference_density
    cp_factor = float(np.clip(1 + 0.08 * density_shift, 0.75, 1.25))
    k_factor = float(np.clip(1 + 0.12 * density_shift, 0.70, 1.30))
    cp_adjusted = max(500.0, base_cp * cp_factor)
    k_adjusted = max(0.01, base_k * k_factor)
    return cp_adjusted, k_adjusted


def get_severity_level(percent_value):
    magnitude = abs(percent_value)
    if magnitude < 1.0:
        return "low", f"Low correction {percent_value:+.2f}%"
    if magnitude < 3.0:
        return "medium", f"Moderate correction {percent_value:+.2f}%"
    return "high", f"High correction {percent_value:+.2f}%"


def get_theoretical_roughness(flow, diameter, mu_val, rho_val):
    area = np.pi * (diameter**2) / 4
    velocity = flow / area
    re = (rho_val * velocity * diameter) / mu_val
    if re <= 2300 or rho_val <= 0:
        return 0.0

    friction_factor = 0.3164 / np.power(re, 0.25)
    friction_velocity = velocity * np.sqrt(friction_factor / 8)
    kinematic_viscosity = mu_val / rho_val
    return max(0.0, (5.0 * kinematic_viscosity) / max(friction_velocity, 1e-12))


fluid_preset = st.sidebar.selectbox("Fluid Preset", list(fluid_presets.keys()), key="fluid_preset")
if "custom_base_density" not in st.session_state:
    st.session_state.custom_base_density = fluid_presets["Custom Manual"]["rho"]
if "custom_base_viscosity" not in st.session_state:
    st.session_state.custom_base_viscosity = fluid_presets["Custom Manual"]["mu"]
if "custom_base_cp" not in st.session_state:
    st.session_state.custom_base_cp = fluid_presets["Custom Manual"]["cp"]
if "custom_base_k" not in st.session_state:
    st.session_state.custom_base_k = fluid_presets["Custom Manual"]["k"]

st.sidebar.markdown("---")
st.sidebar.subheader("Fluid Setup")

if fluid_preset == "Custom Manual":
    st.sidebar.markdown("**Custom Base Properties**")
    st.sidebar.slider("Base Density (kg/m³)", 600.0, 1400.0, key="custom_base_density", step=1.0, format="%.1f")
    st.sidebar.slider("Base Viscosity (Pa·s)", 0.0001, 2.0, key="custom_base_viscosity", step=0.0001, format="%.6f")
    st.sidebar.slider("Base Specific Heat (J/kg.K)", 1000.0, 5000.0, key="custom_base_cp", step=10.0, format="%.1f")
    st.sidebar.slider("Base Conductivity (W/m.K)", 0.01, 1.50, key="custom_base_k", step=0.001, format="%.3f")

rho_temp, cp_temp, k_temp, mu_temp = get_fluid_properties(temp_input, fluid_preset)
rho_base, cp_base_temp, k_base_temp, mu_base = get_fluid_properties(baseline_temp, fluid_preset)

property_source = f"{fluid_preset}:{temp_input:.1f}"
if st.session_state.get("property_source") != property_source:
    st.session_state.manual_density = float(rho_temp)
    st.session_state.manual_viscosity = float(mu_temp)
    st.session_state.property_source = property_source

rho_dyn = st.sidebar.slider("Active Density (kg/m³)", 600.0, 1400.0, key="manual_density", step=1.0, format="%.1f")
st.sidebar.caption(f"Modeled density from preset/temperature: {rho_temp:.1f} kg/m³")
mu_dyn = st.sidebar.slider("Active Viscosity (Pa·s)", 0.0001, 2.0, key="manual_viscosity", step=0.0001, format="%.6f")
st.sidebar.caption(f"Modeled viscosity from preset/temperature: {mu_temp:.6f} Pa·s")

enable_density_correction = st.sidebar.checkbox("Enable Density Correction", value=True, key="enable_density_correction")
if enable_density_correction:
    cp_dyn, k_dyn = apply_density_correction(cp_temp, k_temp, rho_dyn, rho_base)
    cp_base, k_base = apply_density_correction(cp_base_temp, k_base_temp, rho_base, rho_base)
else:
    cp_dyn, k_dyn = cp_temp, k_temp
    cp_base, k_base = cp_base_temp, k_base_temp

cp_density_delta = cp_dyn - cp_temp
k_density_delta = k_dyn - k_temp
density_shift_pct = ((rho_dyn - rho_base) / rho_base) * 100 if rho_base > 0 else 0.0
cp_density_delta_pct = ((cp_dyn - cp_temp) / cp_temp) * 100 if cp_temp > 0 else 0.0
k_density_delta_pct = ((k_dyn - k_temp) / k_temp) * 100 if k_temp > 0 else 0.0
max_density_correction_pct = max(abs(cp_density_delta_pct), abs(k_density_delta_pct))
cp_badge_class, cp_badge_text = get_severity_level(cp_density_delta_pct)
k_badge_class, k_badge_text = get_severity_level(k_density_delta_pct)
viscosity_shift_pct = ((mu_dyn - mu_temp) / mu_temp) * 100 if mu_temp > 0 else 0.0
roughness_theoretical = get_theoretical_roughness(f_input, d_input, mu_dyn, rho_dyn)
roughness_theoretical_microns = roughness_theoretical * 1_000_000


def get_physics(flow, diameter, length, mu_val, rho_val, cp_val, k_val, t_fluid, t_amb):
    area = np.pi * (diameter**2) / 4
    velocity = flow / area
    re = (rho_val * velocity * diameter) / mu_val
    pr = (mu_val * cp_val) / k_val
    
    # --- VECTORIZED HEAT TRANSFER ---
    # np.where allows the charts to calculate 100 points at once without crashing
    nu = np.where(re > 4000, 0.023 * (re**0.8) * (pr**0.4), 3.66)
    h = (nu * k_val) / diameter
    q = h * (np.pi * diameter * length) * (t_fluid - t_amb)
    
    # --- VECTORIZED FRICTION (Haaland Equation) ---
    eps = 0.000045 # Standard Pipe Roughness
    re_safe = np.maximum(re, 1) # Prevent division by zero
    f_turb = (-1.8 * np.log10(((eps/diameter)/3.7)**1.11 + 6.9/re_safe))**-2
    f_lam = 64 / re_safe
    f = np.where(re > 2300, f_turb, f_lam)
    
    dp = f * (length / diameter) * (rho_val * velocity**2 / 2)
    return re, q, dp


re, q_calc, dp_calc = get_physics(
    f_input,
    d_input,
    l_input,
    mu_dyn,
    rho_dyn,
    cp_dyn,
    k_dyn,
    temp_input,
    temp_ambient,
)
roughness_display = f"{roughness_theoretical_microns:,.2f} microns" if re > 2300 else "N/A (laminar)"
energy_label = "Heat Loss" if q_calc >= 0 else "Heat Gain"

if "measured_dp" not in st.session_state:
    st.session_state.measured_dp = float(dp_calc)
if "alert_baseline_dp" not in st.session_state:
    st.session_state.alert_baseline_dp = float(dp_calc)
st.session_state.current_dp_for_sync = float(dp_calc)

st.sidebar.markdown("---")
st.sidebar.subheader("Alert Setup")
measured_dp = st.sidebar.number_input("Instrument Pressure Drop ΔP (Pa)", key="measured_dp", step=10.0)
st.sidebar.button("Sync Sensor To Current Model", on_click=sync_sensor_to_model)
alert_reference_mode = st.sidebar.selectbox(
    "Alert Reference Mode",
    ["Current manual baseline", "Current model snapshot"],
    index=0,
)
if alert_reference_mode == "Current manual baseline":
    baseline_dp = st.sidebar.number_input("Alert Baseline ΔP (Pa)", key="alert_baseline_dp", step=10.0)
else:
    baseline_dp = float(dp_calc)
    st.sidebar.caption(f"Snapshot baseline uses current modeled pressure drop: {baseline_dp:,.1f} Pa")
st.sidebar.button("Set Alert Baseline To Current Pressure", on_click=sync_alert_baseline_to_model)
alert_threshold_pct = st.sidebar.slider("Alert Threshold (%)", 0.5, 10.0, 1.0, step=0.5, format="%.1f")

st.sidebar.markdown("---")
st.sidebar.subheader("📋 Live Parameter Summary")
st.sidebar.caption("Surface roughness is auto-estimated for non-laminar flow and shown in microns.")
st.sidebar.markdown(
    f"""
<table style="width:100%; font-size:0.92rem; border-collapse:collapse;">
    <tr><td><strong>Fluid Preset</strong></td><td style="text-align:right;">{fluid_preset}</td></tr>
  <tr><td><strong>Flow Rate</strong></td><td style="text-align:right;">{f_input:.4f} m³/s</td></tr>
  <tr><td><strong>Pipe Diameter</strong></td><td style="text-align:right;">{d_input:.3f} m</td></tr>
    <tr><td><strong>Pipe Length</strong></td><td style="text-align:right;">{l_input:.1f} m</td></tr>
  <tr><td><strong>Temperature</strong></td><td style="text-align:right;">{temp_input:.1f} °C</td></tr>
        <tr><td><strong>Theoretical Roughness</strong></td><td style="text-align:right;">{roughness_display}</td></tr>
    <tr><td><strong>Modeled Density</strong></td><td style="text-align:right;">{rho_temp:.1f} kg/m³</td></tr>
  <tr><td><strong>Density</strong></td><td style="text-align:right;">{rho_dyn:.1f} kg/m³</td></tr>
    <tr><td><strong>Modeled Viscosity</strong></td><td style="text-align:right;">{mu_temp:.6f} Pa·s</td></tr>
    <tr><td><strong>Viscosity</strong></td><td style="text-align:right;">{mu_dyn:.6f} Pa·s</td></tr>
    <tr><td><strong>Specific Heat</strong></td><td style="text-align:right;">{cp_dyn:,.0f} J/kg.K</td></tr>
    <tr><td><strong>Conductivity</strong></td><td style="text-align:right;">{k_dyn:.3f} W/m.K</td></tr>
  <tr><td><strong>Reynolds No.</strong></td><td style="text-align:right;">{re:,.0f}</td></tr>
  <tr><td><strong>Heat Transfer</strong></td><td style="text-align:right;">{q_calc:,.1f} W</td></tr>
    <tr><td><strong>Modeled Pressure Drop</strong></td><td style="text-align:right;">{dp_calc:,.1f} Pa</td></tr>
    <tr><td><strong>Instrument Pressure Drop</strong></td><td style="text-align:right;">{measured_dp:,.1f} Pa</td></tr>
    <tr><td><strong>Pressure Gap</strong></td><td style="text-align:right;">{measured_dp - dp_calc:+,.1f} Pa</td></tr>
  <tr><td><strong>Alert Baseline ΔP</strong></td><td style="text-align:right;">{baseline_dp:,.1f} Pa</td></tr>
</table>
""",
    unsafe_allow_html=True,
)

deviation = ((measured_dp - baseline_dp) / baseline_dp) * 100 if baseline_dp > 0 else 0.0
regime = "TURBULENT" if re > 4000 else ("LAMINAR" if re < 2300 else "TRANSITION")
comparison_rows = [
    {
        "Property": "Density",
        "Modeled": f"{rho_temp:.1f} kg/m³",
        "Active": f"{rho_dyn:.1f} kg/m³",
        "Delta": f"{rho_dyn - rho_temp:+.1f} kg/m³",
        "Source": "Active Slider",
    },
    {
        "Property": "Viscosity",
        "Modeled": f"{mu_temp:.6f} Pa·s",
        "Active": f"{mu_dyn:.6f} Pa·s",
        "Delta": f"{mu_dyn - mu_temp:+.6f} Pa·s",
        "Source": "Active Slider",
    },
    {
        "Property": "Pressure Drop",
        "Modeled": f"{dp_calc:,.1f} Pa",
        "Active": f"{measured_dp:,.1f} Pa",
        "Delta": f"{measured_dp - dp_calc:+,.1f} Pa",
        "Source": "Instrument Sensor",
    },
]

comparison_csv_buffer = io.StringIO()
comparison_writer = csv.DictWriter(comparison_csv_buffer, fieldnames=["Property", "Modeled", "Active", "Delta", "Source"])
comparison_writer.writeheader()
comparison_writer.writerows(comparison_rows)
comparison_csv = comparison_csv_buffer.getvalue()


st.title("🛡️ Agentic Monitor: Temperature & Density Impact")
st.caption(f"Preset: {fluid_preset} | Active density: {rho_dyn:.1f} kg/m³ | Active viscosity: {mu_dyn:.6f} Pa·s")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Density (ρ)", f"{rho_dyn:.1f} kg/m³")
col2.metric(energy_label, f"{abs(q_calc) / 1000:,.2f} kW", delta=f"{deviation:.1f}% Friction Load")
col3.metric("Reynolds (Re)", f"{re:,.0f}")
col4.metric("Total Pressure Drop", f"{dp_calc / 1000:,.2f} kPa")

st.subheader("Fluid Properties Panel")
st.caption(f"{fluid_preset} provides the base fluid properties at the selected temperature. Active density and viscosity sliders let you adjust the live operating state.")
st.code(
    "cp = cp_temp * clip(1 + 0.08 * ((rho - rho_ref) / rho_ref), 0.75, 1.25)\n"
    "k  = k_temp  * clip(1 + 0.12 * ((rho - rho_ref) / rho_ref), 0.70, 1.30)",
    language="text",
)
prop1, prop2, prop3, prop4 = st.columns(4)
prop1.metric("Temperature", f"{temp_input:.1f} °C", f"vs {baseline_temp:.1f} °C baseline")
prop2.metric("Density", f"{rho_dyn:.1f} kg/m³", f"{density_shift_pct:+.2f}%")
prop3.metric("Specific Heat", f"{cp_dyn:,.0f} J/kg.K", f"{((cp_dyn - cp_base) / cp_base) * 100:+.2f}%")
prop4.metric("Conductivity", f"{k_dyn:.3f} W/m.K", f"{((k_dyn - k_base) / k_base) * 100:+.2f}%")

prop5, prop6, prop7, prop8 = st.columns(4)
prop5.metric("Viscosity", f"{mu_dyn:.6f} Pa·s", f"{viscosity_shift_pct:+.2f}%")
prop6.metric("Cp Temp-Only", f"{cp_temp:,.0f} J/kg.K", f"{cp_density_delta:+.1f} ({cp_density_delta_pct:+.2f}%)")
prop7.metric("k Temp-Only", f"{k_temp:.3f} W/m.K", f"{k_density_delta:+.4f} ({k_density_delta_pct:+.2f}%)")
prop8.metric("Active Controls", "Density + Viscosity", f"ρ {rho_dyn - rho_temp:+.1f} | μ {mu_dyn - mu_temp:+.6f}")

badge1, badge2, badge3, badge4 = st.columns(4)
badge1.markdown("", unsafe_allow_html=True)
if enable_density_correction:
    badge2.markdown(f'<div class="property-badge {cp_badge_class}">{cp_badge_text}</div>', unsafe_allow_html=True)
    badge3.markdown(f'<div class="property-badge {k_badge_class}">{k_badge_text}</div>', unsafe_allow_html=True)
else:
    badge2.markdown('<div class="property-badge disabled">Density correction disabled</div>', unsafe_allow_html=True)
    badge3.markdown('<div class="property-badge disabled">Density correction disabled</div>', unsafe_allow_html=True)
badge4.markdown("", unsafe_allow_html=True)

st.caption("Badge legend: Low < 1% correction, Moderate 1% to < 3%, High >= 3%.")

st.markdown("### Modeled vs Active Comparison")
st.markdown(
        f"""
<table style="width:100%; font-size:0.94rem; border-collapse:collapse;">
  <tr>
    <th style="text-align:left;">Property</th>
    <th style="text-align:right;">Modeled</th>
    <th style="text-align:right;">Active</th>
    <th style="text-align:right;">Delta</th>
    <th style="text-align:right;">Source</th>
  </tr>
  <tr>
    <td><strong>Density</strong></td>
    <td style="text-align:right;">{rho_temp:.1f} kg/m³</td>
    <td style="text-align:right;">{rho_dyn:.1f} kg/m³</td>
    <td style="text-align:right;">{rho_dyn - rho_temp:+.1f} kg/m³</td>
        <td style="text-align:right;">Active Slider</td>
  </tr>
  <tr>
    <td><strong>Viscosity</strong></td>
    <td style="text-align:right;">{mu_temp:.6f} Pa·s</td>
    <td style="text-align:right;">{mu_dyn:.6f} Pa·s</td>
    <td style="text-align:right;">{mu_dyn - mu_temp:+.6f} Pa·s</td>
        <td style="text-align:right;">Active Slider</td>
  </tr>
    <tr>
        <td><strong>Pressure Drop</strong></td>
        <td style="text-align:right;">{dp_calc:,.1f} Pa</td>
        <td style="text-align:right;">{measured_dp:,.1f} Pa</td>
        <td style="text-align:right;">{measured_dp - dp_calc:+,.1f} Pa</td>
        <td style="text-align:right;">Observed Sensor</td>
    </tr>
</table>
""",
    unsafe_allow_html=True,
)
st.download_button(
        "Download Comparison CSV",
        data=comparison_csv,
        file_name="modeled_vs_active_comparison.csv",
        mime="text/csv",
)

if max_density_correction_pct < 1.0:
    if enable_density_correction:
        st.success(f"Density correction is low. Maximum property correction is {max_density_correction_pct:.2f}%.")
elif max_density_correction_pct < 3.0:
    if enable_density_correction:
        st.warning(f"Density correction is moderate. Maximum property correction is {max_density_correction_pct:.2f}%.")
else:
    if enable_density_correction:
        st.error(f"Density correction is high. Maximum property correction is {max_density_correction_pct:.2f}%. Review measured density input.")

if not enable_density_correction:
    st.info("Density correction is disabled. Specific heat and conductivity are using temperature-only values.")

if regime == "LAMINAR":
    st.info("Flow Regime: LAMINAR. Heat transfer and pressure behavior are smoother, but sensitivity to wall effects is lower.")
elif regime == "TRANSITION":
    st.warning("Flow Regime: TRANSITION. Small changes in operating conditions can shift hydraulic behavior quickly.")
else:
    st.success("Flow Regime: TURBULENT. Mixing is stronger and pressure-drop sensitivity is higher.")

st.markdown("---")
if temp_input > 60:
    st.warning(
        f"⚠️ High Temp Alert: Modeled density at this temperature is {rho_temp:.1f} kg/m³. Heat carrying capacity is reduced by expansion."
    )

if abs(deviation) >= alert_threshold_pct:
    st.error(
        f"🚨 Pressure Alert: Observed pressure drop deviates by {abs(deviation):.1f}% from the alert baseline."
    )
else:
    st.success(f"✅ Pressure is within {alert_threshold_pct:.1f}% of the alert baseline.")


# --- AGENTIC ANOMALY DETECTION ---
st.markdown("---")
physics_deviation = ((measured_dp - dp_calc) / dp_calc) * 100 if dp_calc > 0 else 0.0

if abs(physics_deviation) >= 1.0:  # The 1% Threshold
    st.error(f"🚨 ANOMALY: {physics_deviation:+.1f}% Pressure Deviation Detected.")
    if re > 4000:
        st.info("Agent Reasoning: Flow is Turbulent. High deviation suggests internal pipe fouling or scaling.")
    else:
        st.info("Agent Reasoning: Flow is Laminar. Deviation suggests a partial physical blockage or sensor drift.")
else:
    st.success("✅ SYSTEM HEALTHY: Sensor is within 1% of Physics Baseline.")


st.subheader("Calculated Values")
val1, val2, val3, val4 = st.columns(4)
val1.metric("Viscosity (μ)", f"{mu_dyn:.6f} Pa·s")
val2.metric("Modeled Pressure Drop", f"{dp_calc / 1000:,.2f} kPa")
val3.metric("Specific Heat (Cp)", f"{cp_dyn:,.0f} J/kg.K")
val4.metric("Conductivity (k)", f"{k_dyn:.3f} W/m.K")


st.subheader("Pressure Drop & Heat Transfer Across Pipe Length")
st.caption(
    "Cumulative ΔP and Q from 0 → pipe length. In this simplified model, properties and boundary conditions "
    "are assumed uniform, so ΔP and Q scale linearly with length."
)

length_axis = np.linspace(0.0, float(l_input), 120)
_, q_len_curve, dp_len_curve = get_physics(
    f_input,
    d_input,
    length_axis,
    mu_dyn,
    rho_dyn,
    cp_dyn,
    k_dyn,
    temp_input,
    temp_ambient,
)

q_per_m = (q_calc / l_input) if l_input > 0 else 0.0
dp_per_m = (dp_calc / l_input) if l_input > 0 else 0.0

len1, len2, len3, len4 = st.columns(4)
len1.metric("Heat transfer rate", f"{q_per_m / 1000:,.3f} kW/m")
len2.metric("Pressure drop rate", f"{dp_per_m / 1000:,.3f} kPa/m")
len3.metric(energy_label + " (total)", f"{abs(q_calc) / 1000:,.2f} kW")
len4.metric("Total ΔP", f"{dp_calc / 1000:,.2f} kPa")

fig_len, (ax_q_len, ax_dp_len) = plt.subplots(1, 2, figsize=(10, 4))

ax_q_len.plot(length_axis, q_len_curve / 1000, color="steelblue", linewidth=2)
ax_q_len.set_xlabel("Pipe Length (m)")
ax_q_len.set_ylabel("Cumulative Heat Transfer (kW)")
ax_q_len.grid(True, alpha=0.25)

ax_dp_len.plot(length_axis, dp_len_curve / 1000, color="darkorange", linewidth=2)
ax_dp_len.set_xlabel("Pipe Length (m)")
ax_dp_len.set_ylabel("Cumulative Pressure Drop (kPa)")
ax_dp_len.grid(True, alpha=0.25)

plt.tight_layout()
st.pyplot(fig_len)


flow_range = np.linspace(0.0001, 0.01, 100)
re_curve, q_curve, dp_curve = get_physics(flow_range, d_input, l_input, mu_dyn, rho_dyn, cp_dyn, k_dyn, temp_input, temp_ambient)

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(flow_range, q_curve, color="steelblue", label="Heat Transfer")
ax.scatter([f_input], [q_calc], color="red", s=80, label="Current Point")
ax.set_xlabel("Flow Rate (m³/s)")
ax.set_ylabel("Heat Transfer (W)")
ax.legend()
st.pyplot(fig)


st.subheader("Pressure Drop Diagnostic Curve")
fig_dp, ax_dp = plt.subplots(figsize=(10, 4))
ax_dp.plot(flow_range, dp_curve, color="darkorange", label="Modeled Pressure Drop")
ax_dp.scatter([f_input], [measured_dp], color="red", s=80, label="Instrument Pressure")
ax_dp.scatter([f_input], [dp_calc], color="navy", s=60, label="Current Model")
ax_dp.set_xlabel("Flow Rate (m³/s)")
ax_dp.set_ylabel("Pressure Drop (Pa)")
ax_dp.legend()
st.pyplot(fig_dp)


st.subheader("Reynolds Number Diagnostic Curve")
fig_re, ax_re = plt.subplots(figsize=(10, 4))
ax_re.plot(flow_range, re_curve, color="seagreen", label="Reynolds Number")
ax_re.scatter([f_input], [re], color="purple", s=80, label="Current Point")
ax_re.axhline(2300, color="gray", linestyle="--", linewidth=1, label="Laminar Limit")
ax_re.axhline(4000, color="black", linestyle=":", linewidth=1, label="Turbulent Threshold")
ax_re.set_xlabel("Flow Rate (m³/s)")
ax_re.set_ylabel("Reynolds Number")
ax_re.legend()
st.pyplot(fig_re)
