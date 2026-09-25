"""Decodificación estricta: nunca imputa ausencias desconocidas."""

from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data/gov_10a_exp_eu27_2015_2024.json"
EU27 = "AT BE BG CY CZ DE DK EE EL ES FI FR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split()
YEARS = list(range(2015, 2025))
SECTORS = ["S1311", "S1312", "S1313", "S1314"]
SHARES = ["share_central", "share_state", "share_local", "share_social_security"]
STATE_COUNTRIES = {"AT", "BE", "DE", "ES"}
GLOSSARY = "https://ec.europa.eu/eurostat/statistics-explained/SEPDF/cache/1123.pdf"
MALTA = "https://nso.gov.mt/wp-content/uploads/2023/01/EDP-Inventory-ESA-2010.pdf"


def decode_snapshot(path=RAW_PATH):
    """Preserva value y status, también para posiciones sin número."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    categories = {}
    for dim in data["id"]:
        index = data["dimension"][dim]["category"]["index"]
        if isinstance(index, dict):
            categories[dim] = sorted(index, key=index.get)
        else:
            categories[dim] = index
    rows = []
    # Eurostat puede publicar una marca estadística sin un valor numérico.
    # Se leen ambas listas para no perder esas observaciones.
    value_positions = set(data["value"])
    status_positions = set(data.get("status", {}))
    positions = sorted(value_positions | status_positions, key=int)
    for pos in positions:
        coords = np.unravel_index(int(pos), data["size"])
        row = {}
        for dim, coord in zip(data["id"], coords):
            row[dim] = categories[dim][coord]
        row.update(
            value=data["value"].get(pos, np.nan),
            status=data.get("status", {}).get(pos, ""),
        )
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame["time"] = frame["time"].astype(int)
    return frame, data


def classify_period(year):
    """La fase aguda se conserva, pero no entra en la comparación principal."""
    if 2017 <= year <= 2019:
        return "pre"
    elif 2020 <= year <= 2021:
        return "covid"
    elif 2022 <= year <= 2024:
        return "post"
    else:
        return "context"


def prepare(raw, unit="PC_GDP"):
    # Misma cobertura para todos los países: gasto total anual, 2015–2024.
    selected = (
        (raw["unit"] == unit)
        & (raw["freq"] == "A")
        & (raw["cofog99"] == "TOTAL")
        & (raw["na_item"] == "TE")
        & raw["geo"].isin(EU27)
        & raw["time"].isin(YEARS)
    )
    frame = raw.loc[selected].copy()
    keys = ["geo", "time", "sector"]
    if frame.duplicated(keys).any():
        raise ValueError("Claves país-año-subsector duplicadas")
    # Se incluyen todas las combinaciones esperadas para detectar los huecos.
    index = pd.MultiIndex.from_product([EU27, YEARS, ["S13"] + SECTORS], names=keys)
    audit = frame.set_index(keys)[["value", "status"]].reindex(index).reset_index()
    audit["status"] = audit["status"].fillna("")
    no_regional_sector = (audit["sector"] == "S1312") & ~audit["geo"].isin(
        STATE_COUNTRIES
    )
    no_social_sector = (audit["sector"] == "S1314") & (audit["geo"] == "MT")
    allowed = no_regional_sector | no_social_sector
    missing = audit["value"].isna()

    # Un dato desconocido fuera de estos casos no se puede tratar como cero.
    unknown_missing = missing & ~allowed
    if unknown_missing.any():
        cases = audit.loc[unknown_missing, keys].to_json(orient="records")
        raise ValueError("Ausencia no documentada: " + cases)
    conflicting_value = allowed & audit["value"].notna() & (audit["value"] != 0)
    if conflicting_value.any():
        raise ValueError(
            "La instantánea contradice el mapa institucional: revisar fuentes"
        )

    # Se conserva value para distinguir lo publicado de lo utilizado en el cálculo.
    audit["treatment"] = "valor_publicado"
    audit.loc[missing, "treatment"] = "cero_estructural_documentado"
    audit["source_rule"] = "Eurostat gov_10a_exp"
    audit.loc[missing & no_regional_sector, "source_rule"] = GLOSSARY
    audit.loc[missing & no_social_sector, "source_rule"] = MALTA
    audit["analysis_value"] = audit["value"].copy()
    audit.loc[missing, "analysis_value"] = 0
    audit["unit"] = unit
    wide = audit.pivot(
        index=["geo", "time"], columns="sector", values="analysis_value"
    ).reset_index()
    wide.columns.name = None
    if (
        not np.isfinite(wide[["S13"] + SECTORS].to_numpy()).all()
        or (wide[["S13"] + SECTORS] < 0).any().any()
    ):
        raise ValueError("Gastos no finitos o negativos")
    wide["subsector_total"] = wide[SECTORS].sum(axis=1, min_count=4)
    if not wide["subsector_total"].gt(0).all():
        raise ValueError("Denominador no positivo")
    for sector, share in zip(SECTORS, SHARES):
        wide[share] = 100 * wide[sector] / wide["subsector_total"]
    wide["share_central_social"] = wide["share_central"] + wide["share_social_security"]
    wide["period"] = wide["time"].apply(classify_period)
    np.testing.assert_allclose(wide[SHARES].sum(axis=1), 100)
    assert len(wide) == 270 and not wide.duplicated(["geo", "time"]).any()
    return wide, audit


def main():
    raw, _ = decode_snapshot()
    out = ROOT / ".resultados/datos"
    out.mkdir(parents=True, exist_ok=True)
    for unit, suffix in [("PC_GDP", ""), ("MIO_EUR", "_eur")]:
        wide, audit = prepare(raw, unit)
        wide.to_csv(out / f"gov_expenditure_composition{suffix}.csv", index=False)
        audit.to_csv(out / f"auditoria_observaciones{suffix}.csv", index=False)
    print("Paneles y auditoría regenerados desde la instantánea conservada.")


if __name__ == "__main__":
    main()
