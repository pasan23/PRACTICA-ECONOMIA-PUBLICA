"""Funciones compartidas por cuadernos, tablas y figuras de entrega."""

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from src.prepare_data import SHARES

LABELS = {
    "share_central": "Central",
    "share_state": "Regional (S.1312)",
    "share_local": "Local",
    "share_social_security": "Seguridad social",
}
NAMES = {
    "AT": "Austria",
    "BE": "Bélgica",
    "BG": "Bulgaria",
    "CY": "Chipre",
    "CZ": "Chequia",
    "DE": "Alemania",
    "DK": "Dinamarca",
    "EE": "Estonia",
    "EL": "Grecia",
    "ES": "España",
    "FI": "Finlandia",
    "FR": "Francia",
    "HR": "Croacia",
    "HU": "Hungría",
    "IE": "Irlanda",
    "IT": "Italia",
    "LT": "Lituania",
    "LU": "Luxemburgo",
    "LV": "Letonia",
    "MT": "Malta",
    "NL": "Países Bajos",
    "PL": "Polonia",
    "PT": "Portugal",
    "RO": "Rumanía",
    "SE": "Suecia",
    "SI": "Eslovenia",
    "SK": "Eslovaquia",
}

# S.1312 se describe, pero no se contrasta: solo existe separado en cuatro países.
MAIN = ["share_central", "share_local", "share_social_security"]
WINDOWS = [
    ("Principal", (2017, 2019), (2022, 2024)),
    ("Base amplia", (2015, 2019), (2022, 2024)),
    ("Trienio inicial", (2015, 2017), (2022, 2024)),
    ("Bienios próximos", (2018, 2019), (2022, 2023)),
    ("Bienio reciente", (2018, 2019), (2023, 2024)),
    ("Extremos anuales", (2019, 2019), (2024, 2024)),
    ("Fase aguda", (2017, 2019), (2020, 2021)),
    ("Evolución posterior", (2020, 2021), (2022, 2024)),
    ("Referencia precrisis", (2015, 2016), (2018, 2019)),
]


def period_mean(wide, years, columns=SHARES):
    """Calcula la media de cada país, dando el mismo peso a cada año."""
    first_year, last_year = years
    selected = wide[wide["time"].between(first_year, last_year)]
    expected_years = last_year - first_year + 1

    # Un país con menos años tendría una comparación distinta a la de los demás.
    observations = selected.groupby("geo").size()
    duplicated = selected.duplicated(["geo", "time"]).any()
    complete_years = observations.eq(expected_years).all()
    same_countries = set(selected["geo"]) == set(wide["geo"])
    if duplicated or not complete_years or not same_countries:
        raise ValueError("Ventana incompleta o claves duplicadas")
    if selected[columns].isna().any().any():
        raise ValueError("Cuotas ausentes en ventana")

    period_means = selected.groupby("geo")[columns].mean()
    return period_means.sort_index()


def changes(wide, pre=(2017, 2019), post=(2022, 2024)):
    """Resta la participación anterior de la posterior para cada país."""
    pre_means = period_mean(wide, pre)
    post_means = period_mean(wide, post)
    delta = post_means - pre_means

    # Solo entran las cuatro cuotas: el índice no se incluye en su propio cálculo.
    # Dividir entre dos evita contar dos veces lo que un subsector gana y otro pierde.
    delta["reallocation_index"] = delta[SHARES].abs().sum(axis=1) / 2
    np.testing.assert_allclose(delta[SHARES].sum(axis=1), 0, atol=1e-10)
    return delta


def inference(delta):
    """Contrasta las diferencias nacionales, no las observaciones anuales."""
    results = []
    for variable in MAIN:
        x = delta[variable]
        n = len(x)
        mean_change = x.mean()
        standard_error = stats.sem(x)

        ci_low, ci_high = stats.t.interval(
            0.95, df=n - 1, loc=mean_change, scale=standard_error
        )
        t_test = stats.ttest_1samp(x, popmean=0)
        wilcoxon = stats.wilcoxon(
            x, zero_method="wilcox", alternative="two-sided", method="auto"
        )
        results.append(
            {
                "sector": variable,
                "n": n,
                "mean_change": mean_change,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "p_ttest": t_test.pvalue,
                "p_wilcoxon": wilcoxon.pvalue,
            }
        )

    results_df = pd.DataFrame(results)
    # Cada procedimiento forma su propia familia de tres contrastes.
    results_df["p_ttest_holm"] = multipletests(results_df["p_ttest"], method="holm")[1]
    results_df["p_wilcoxon_holm"] = multipletests(
        results_df["p_wilcoxon"], method="holm"
    )[1]
    return results_df


def temporal_sensitivity(wide):
    """Repite la comparación con las nueve ventanas fijadas arriba."""
    results = []
    for label, pre, post in WINDOWS:
        delta = changes(wide, pre, post)
        mean_changes = delta[SHARES].mean()
        row = {
            "specification": label,
            "pre": f"{pre[0]}–{pre[1]}",
            "post": f"{post[0]}–{post[1]}",
        }
        for variable in SHARES:
            row[variable] = mean_changes[variable]
        row["central_increases"] = int((delta["share_central"] > 0).sum())
        row["mean_reallocation"] = delta["reallocation_index"].mean()
        results.append(row)
    return pd.DataFrame(results)


def leave_one_out(delta):
    """Comprueba cuánto cambia la media al retirar un país cada vez."""
    results = []
    for country in delta.index:
        remaining = delta.drop(country)
        mean_changes = remaining[SHARES].mean()
        row = {"excluded": country}
        for variable in SHARES:
            row[variable] = mean_changes[variable]
        results.append(row)
    return pd.DataFrame(results)


def grouped_change(wide):
    """Comprobación secundaria de clasificación, con el mismo denominador."""
    columns = ["share_central_social"]
    pre = period_mean(wide, (2017, 2019), columns)
    post = period_mean(wide, (2022, 2024), columns)
    delta = post - pre
    return delta.rename(columns={"share_central_social": "central_social_change"})
