# Heat Transfer Dashboard

Industrial pipe-side digital twin for thermal and hydraulic monitoring with preset fluids, live property overrides, alert baselines, and diagnostic comparisons.

This project is a Streamlit-based industrial pipe monitoring dashboard for evaluating:

- pressure drop
- heat transfer
- preset-based fluid properties
- baseline deviation alerts

The application models a pipe section and shows how operating conditions affect Reynolds number, heat transfer rate, pressure drop, and pressure-alert status.

It is designed for quick engineering review of how temperature, density, viscosity, and fluid selection shift both heat-transfer and pressure-drop behavior in a monitored pipe section.

## Highlights

- Preset fluids plus a custom manual mode
- Always-visible active density and viscosity controls
- Pressure baseline monitoring and virtual sensor comparison
- CSV export for modeled-versus-active values

## Main Features

- Fluid presets for Custom Manual, Water, Light Oil, Heavy Oil, and Glycerin
- Temperature-driven preset properties
- Temperature- and density-adjusted specific heat and thermal conductivity
- Reset to default button
- Reset fluid properties button
- Pressure-drop alerting against a manual or current snapshot baseline
- Virtual observed pressure sensor input
- Always-visible active density slider
- Always-visible active viscosity slider
- Density-correction enable/disable toggle
- Flow regime indication: laminar, transition, turbulent
- Fluid properties panel with temperature-baseline comparison
- CSV export for modeled-versus-active comparison data
- Heat-transfer and pressure-drop plots
- Reynolds-number diagnostic plot
- Live parameter summary in the sidebar

## File

- `main.py`: Streamlit app entry point

## Requirements

Install these Python packages in the project environment:

```powershell
pip install streamlit numpy matplotlib
```

If you are using the local virtual environment in this folder, activate it first:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Run The App

Recommended:

```powershell
streamlit run main.py
```

If you want to use the workspace virtual environment directly:

```powershell
.\.venv\Scripts\python.exe -m streamlit run main.py
```

After launch, Streamlit will open the app in your browser, usually at:

```text
http://localhost:8501
```

## Inputs In The Dashboard

The sidebar lets you configure:

- reset to default
- reset fluid properties
- fluid preset
- flow rate
- pipe diameter
- fluid temperature
- surface roughness
- active density slider
- active viscosity slider
- density-correction toggle
- observed pressure drop
- alert baseline mode and threshold

## Outputs Shown

The dashboard reports:

- density
- viscosity
- preset-adjusted modeled density and viscosity
- modeled reference captions for active density and viscosity sliders
- specific heat
- thermal conductivity
- temperature-only versus density-corrected property view
- modeled-versus-active density and viscosity comparison
- modeled-versus-active pressure-drop comparison
- density-correction severity status
- Reynolds number
- flow regime text
- fluid property baseline deltas
- heat transfer rate
- pressure drop
- deviation from baseline pressure drop
- temperature and pressure alerts

## Notes

- Surface roughness is user-adjustable in the current version.
- Custom Manual, Water, Light Oil, Heavy Oil, and Glycerin presets are available.
- Specific heat is calculated from the current fluid temperature and then adjusted by density shift.
- Thermal conductivity is calculated from the current fluid temperature and then adjusted by density shift.
- The fluid properties panel shows both the temperature-based values and the density correction contribution.
- The panel also displays the exact density-correction formulas and a low/moderate/high correction status.
- The panel includes color-coded correction badges and a modeled-versus-active comparison table for density and viscosity.
- Density and viscosity are always editable through active sliders, even when a preset is selected.
- The active density and viscosity sliders show the preset-modeled reference values directly beneath them.
- The comparison section also includes pressure drop, a CSV download button, and a legend for badge thresholds.
- Run the app with Streamlit, not with `python main.py`.

## Purpose

This app is intended for quick engineering exploration and operator-style monitoring of how changing fluid conditions can influence hydraulic and thermal performance in a pipe.