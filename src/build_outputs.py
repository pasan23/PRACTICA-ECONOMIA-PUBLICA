"""Genera evidencia, gráficos vectoriales y cifras LaTeX desde los mismos cálculos."""

from pathlib import Path
import json
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter
from src.prepare_data import ROOT, SHARES
from src.analysis import (
    LABELS,
    NAMES,
    changes,
    inference,
    temporal_sensitivity,
    leave_one_out,
    grouped_change,
    period_mean,
)

OUT = ROOT / ".resultados/pdf"
TABLES = ROOT / ".resultados/tablas"
FIGURES = ROOT / ".resultados/figuras"


def fmt(x, n=3):
    return f"{x:.{n}f}".replace(".", ",")


def write_rows(name, rows):
    """Escribe las filas de una tabla con el formato que necesita LaTeX."""
    lines = []
    for row in rows:
        values = []
        for value in row:
            values.append(str(value))
        line = " & ".join(values) + r" \\" + "\n"
        lines.append(line)
    path = OUT / "tablas" / name
    path.write_text("".join(lines), encoding="utf-8")


def main():
    # 1. Leer los dos paneles y calcular los resultados con las mismas funciones.
    for folder in [OUT / "tablas", OUT / "figuras", TABLES, FIGURES]:
        folder.mkdir(parents=True, exist_ok=True)
    wide = pd.read_csv(ROOT / ".resultados/datos/gov_expenditure_composition.csv")
    wide_eur = pd.read_csv(
        ROOT / ".resultados/datos/gov_expenditure_composition_eur.csv"
    )
    delta = changes(wide)
    delta_eur = changes(wide_eur)
    results_df = inference(delta)
    windows = temporal_sensitivity(wide)
    loo = leave_one_out(delta)
    trend = wide.groupby("time")[SHARES + ["share_central_social"]].mean()
    grouped = grouped_change(wide)

    periods = [("pre", (2017, 2019)), ("covid", (2020, 2021)), ("post", (2022, 2024))]
    period_results = {}
    for period, years in periods:
        country_means = period_mean(wide, years)
        period_results[period] = country_means.mean()
    summary = pd.DataFrame(period_results)
    summary["change"] = delta[SHARES].mean()

    # Se excluyen los mismos países que en el cuaderno, sin cambiar sus datos.
    samples = [
        ("Todos", []),
        ("Sin Malta", ["MT"]),
        ("Sin Finlandia", ["FI"]),
        ("Sin Eslovaquia", ["SK"]),
        ("Sin Irlanda", ["IE"]),
        ("Sin FI, SK e IE", ["FI", "SK", "IE"]),
    ]
    quality_results = []
    for name, excluded in samples:
        selected = delta.drop(excluded)
        mean_changes = selected[SHARES].mean()
        row = {"sample": name, "n": len(selected)}
        for share in SHARES:
            row[share] = mean_changes[share]
        quality_results.append(row)
    quality = pd.DataFrame(quality_results)

    # 2. Guardar las tablas completas antes de redondearlas para el informe.
    tables = [
        ("cambios_pais", delta),
        ("contrastes", results_df),
        ("serie_anual", trend),
        ("periodos", summary),
        ("sensibilidad_temporal", windows),
        ("exclusiones", loo),
        ("central_y_ss", grouped),
        ("sensibilidad_calidad", quality),
        ("sensibilidad_euros", delta_eur),
    ]
    for name, frame in tables:
        frame.to_csv(TABLES / f"{name}.csv", index=True)

    rows = []
    for share in SHARES:
        row = [LABELS[share]]
        for column in ["pre", "covid", "post", "change"]:
            row.append(fmt(summary.loc[share, column]))
        rows.append(row)
    write_rows("periodos.tex", rows)

    rows = []
    for result in results_df.itertuples():
        interval = f"[{fmt(result.ci_low)}; {fmt(result.ci_high)}]"
        rows.append(
            [
                LABELS[result.sector],
                fmt(result.mean_change),
                interval,
                fmt(result.p_ttest_holm, 4),
                fmt(result.p_wilcoxon_holm, 4),
            ]
        )
    write_rows("contrastes.tex", rows)

    rows = []
    for country, result in delta.iterrows():
        row = [NAMES[country]]
        for column in SHARES + ["reallocation_index"]:
            row.append(fmt(result[column]))
        row.append(fmt(grouped.loc[country, "central_social_change"]))
        rows.append(row)
    write_rows("paises.tex", rows)

    rows = []
    for result in windows.itertuples():
        rows.append(
            [
                result.specification,
                result.pre.replace("–", "--"),
                result.post.replace("–", "--"),
                fmt(result.share_central),
                result.central_increases,
            ]
        )
    write_rows("ventanas.tex", rows)

    rows = []
    for _, result in quality.iterrows():
        rows.append(
            [
                result["sample"],
                result["n"],
                fmt(result["share_central"]),
                fmt(result["share_local"]),
                fmt(result["share_social_security"]),
            ]
        )
    write_rows("calidad.tex", rows)

    # 3. Dibujar las cinco figuras. El formato se mantiene igual al del informe.
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#25313A",
            "text.color": "#25313A",
            "pdf.fonttype": 42,
            "axes.titlesize": 11,
        }
    )
    decimal = FuncFormatter(lambda v, p: f"{v:g}".replace(".", ","))

    def save(fig, name):
        fig.savefig(
            OUT / "figuras" / f"{name}.pdf",
            bbox_inches="tight",
            metadata={"CreationDate": datetime(2026, 9, 24, tzinfo=timezone.utc)},
        )
        fig.savefig(FIGURES / f"{name}.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    fig, axs = plt.subplots(2, 2, figsize=(8.2, 5.3), sharex=True)
    for ax, s in zip(axs.flat, SHARES):
        ax.axvspan(2019.5, 2021.5, color="#e8edf0", zorder=0)
        ax.plot(trend.index, trend[s], color="#20566F", marker="o", ms=4, lw=1.7)
        ax.set_title(
            {
                "share_central": "Gobierno central",
                "share_state": "Gobierno regional (S.1312)",
                "share_local": "Gobiernos locales",
                "share_social_security": "Fondos de seguridad social",
            }[s],
            loc="left",
        )
        ax.set_xticks([2015, 2017, 2019, 2021, 2024])
        ax.set_ylabel("Participación (%)")
        ax.grid(axis="y", alpha=0.2)
        ax.yaxis.set_major_formatter(decimal)
    fig.tight_layout()
    save(fig, "serie_anual")
    # Intervalos individuales de los cambios medios.
    fig, ax = plt.subplots(figsize=(8.2, 3.2))
    ax.axvline(0, color="#69747b", lw=1)
    ax.errorbar(
        results_df.mean_change,
        [2, 1, 0],
        xerr=[
            results_df.mean_change - results_df.ci_low,
            results_df.ci_high - results_df.mean_change,
        ],
        fmt="o",
        capsize=5,
        color="#20566F",
    )
    ax.set_yticks(
        [2, 1, 0], ["Gobierno central", "Gobiernos locales", "Seguridad social"]
    )
    ax.set_xlabel("Variación de la participación en el gasto e IC del 95 % (pp)")
    ax.grid(axis="x", alpha=0.2)
    ax.xaxis.set_major_formatter(decimal)
    ax.set_ylim(-0.5, 2.5)
    fig.tight_layout()
    save(fig, "intervalos")
    # Países ordenados por el cambio en la participación del gobierno central.
    order = delta["share_central"].sort_values().index
    fig, ax = plt.subplots(figsize=(8.2, 7.0))
    positions = np.arange(len(order))
    ax.axvline(0, color="#69747b", lw=0.8)
    ax.hlines(positions, 0, delta.loc[order, "share_central"], color="#c0c7cc", lw=1)
    ax.scatter(
        delta.loc[order, "share_central"],
        positions,
        color="#20566F",
        s=24,
        label="Gobierno central",
        zorder=3,
    )
    ax.set_yticks(positions, [NAMES[c] for c in order], fontsize=9)
    ax.set_xlabel("Cambio 2022–2024 frente a 2017–2019 (pp)")
    ax.grid(axis="x", alpha=0.15)
    ax.xaxis.set_major_formatter(decimal)
    ax.legend(loc="lower right", fontsize=9, frameon=False)
    fig.tight_layout()
    save(fig, "comparacion_paises")
    # Cambios de las cuatro participaciones, con una escala común.
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(8.2, 8.2))
    heatmap_data = delta[SHARES].copy()
    heatmap_data.index = [NAMES[c] for c in heatmap_data.index]
    heatmap_data.columns = list(LABELS.values())
    cmap = LinearSegmentedColormap.from_list(
        "signed", ["#20566F", "#FAFAF8", "#A46A32"]
    )
    sns.heatmap(
        heatmap_data,
        cmap=cmap,
        center=0,
        vmin=-7,
        vmax=7,
        annot=heatmap_data.map(lambda v: fmt(v, 2)),
        fmt="",
        linewidths=0.5,
        annot_kws={"size": 9},
        cbar_kws={"label": "Cambio (pp)", "shrink": 0.65},
        ax=ax,
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(axis="both", length=0)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    fig.tight_layout()
    save(fig, "mapa_cambios")
    fig, ax = plt.subplots(figsize=(8.2, 3.1))
    main_windows = windows.iloc[:6]
    ax.axvline(0, color="#69747b", lw=0.8)
    ax.scatter(main_windows.share_central, range(6), color="#20566F")
    ax.set_yticks(range(6), main_windows.specification)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.7)
    ax.set_xlabel("Variación de la participación del gobierno central (pp)")
    ax.xaxis.set_major_formatter(decimal)
    for y, v in enumerate(main_windows.share_central):
        ax.text(v + 0.035, y, fmt(v, 2), va="center", fontsize=9)
    fig.tight_layout()
    save(fig, "ventanas")
    # Cifras narrativas autogeneradas: evitan transcripciones manuales obsoletas.
    macros = {
        "Central": delta["share_central"].mean(),
        "Local": delta["share_local"].mean(),
        "Social": delta["share_social_security"].mean(),
        "Regional": delta["share_state"].mean(),
        "Reasignacion": delta["reallocation_index"].mean(),
        "Agrupado": grouped.central_social_change.mean(),
        "EuroCentral": delta_eur["share_central"].mean(),
        "MinLoo": loo["share_central"].min(),
        "MaxLoo": loo["share_central"].max(),
        "Espana": delta.loc["ES", "share_central"],
        "Chipre": delta.loc["CY", "share_central"],
        "ChipreAgrupado": grouped.loc["CY", "central_social_change"],
        "Previa": windows.iloc[-1].share_central,
        "VentanaMin": windows.iloc[:6].share_central.min(),
        "VentanaMax": windows.iloc[:6].share_central.max(),
        "BaseAmplia": windows.iloc[1].share_central,
        "CentralLow": results_df.iloc[0].ci_low,
        "CentralHigh": results_df.iloc[0].ci_high,
        "PHolm": results_df.iloc[0].p_ttest_holm,
        "CentralPre": summary.loc["share_central", "pre"],
        "CentralPost": summary.loc["share_central", "post"],
        "Calidad": quality.iloc[-1].share_central,
    }
    lines = []
    for name, value in macros.items():
        decimals = 4 if name == "PHolm" else 3
        formatted_value = fmt(value, decimals)
        line = "\\newcommand{\\dato" + name + "}{" + formatted_value + "}\n"
        lines.append(line)
    (OUT / "cifras.tex").write_text("".join(lines), encoding="utf-8")
    (TABLES / "resumen.json").write_text(
        json.dumps(macros, ensure_ascii=False, indent=2)
    )
    print("Tablas, cifras narrativas y cinco figuras reproducidas.")


if __name__ == "__main__":
    main()
