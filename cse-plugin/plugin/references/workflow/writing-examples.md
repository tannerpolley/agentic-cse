# Writing examples

## Example: heater operating cost

For a steady single-phase electric heater with specified inlet and outlet
temperatures $T_{\mathrm{in}}$ and $T_{\mathrm{out}}$ (K), the property model
uses constant specific heat capacity $c_p$ (kJ/(kg K)).

$$
\Delta h = c_p(T_{\mathrm{out}}-T_{\mathrm{in}}). \tag{1}
$$

The enthalpy rise $\Delta h$ (kJ/kg) is the **property-model output** and a
**heater input** alongside mass flow $\dot m$ (kg/s). The heater outputs the
thermal duty $\dot Q$ (kW).

$$
\dot Q = \dot m\,\Delta h. \tag{2}
$$

With electrical-to-thermal efficiency $\eta$ (dimensionless) and electricity
price $p_e$ (2024 USD/kWh), the reported operating cost rate $\dot C$ (2024
USD/h) follows from the duty of Eq. (2).

$$
\dot C = p_e\,\dot Q/\eta. \tag{3}
$$

## Example manuscript

Exact label approval in `STYLE.md`.

```markdown
## Example manuscript
Sources: manuscript/*.tex; figures/plot.py
| Scope | Standing owner decision | Authority |
| --- | --- | --- |
| manuscript/*.tex; figures/plot.py | Approved scientific labels: `F2`; `A1` | Dated explicit owner approval, meaning and source |
```

## Example source paragraph

```latex
% P:introduction-05
Reported batch extraction percentages do not define a process model for this solvent.
Lithium and sodium partition between two nonideal liquids while the extractants compete for finite inventory.
The reactive liquid-liquid-equilibrium calculation resolves those coupled effects.
```

The three source lines render as one paragraph because no blank line separates
them.

## Example review row

Generated review output stays outside manuscript source.

| Source identifier | Idea | Role | Transition to next | Explanation |
|---|---|---|---|---|
| introduction-05.s2 | finite extractant inventory | explains coupling | weak | State how inventory couples the two partition calculations. |
