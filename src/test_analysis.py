"""Controles de fallos que alterarían las conclusiones."""

import unittest
import numpy as np
from src.prepare_data import decode_snapshot, prepare, SHARES
from src.analysis import changes, period_mean


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw, _ = decode_snapshot()
        cls.wide, cls.audit = prepare(cls.raw)

    def test_unknown_missing_stops(self):
        raw = self.raw.copy()
        mask = (
            (raw.unit == "PC_GDP")
            & (raw.geo == "ES")
            & (raw.time == 2019)
            & (raw.sector == "S1311")
        )
        raw.loc[mask, "value"] = np.nan
        with self.assertRaisesRegex(ValueError, "Ausencia no documentada"):
            prepare(raw)

    def test_institutional_conflict_stops(self):
        raw = self.raw.copy()
        mask = (
            (raw.unit == "PC_GDP")
            & (raw.geo == "MT")
            & (raw.time == 2019)
            & (raw.sector == "S1314")
        )
        self.assertTrue(mask.any())
        raw.loc[mask, "value"] = 1
        with self.assertRaisesRegex(ValueError, "contradice"):
            prepare(raw)

    def test_incomplete_period_stops(self):
        short = self.wide[~((self.wide.geo == "ES") & (self.wide.time == 2018))]
        with self.assertRaisesRegex(ValueError, "incompleta"):
            period_mean(short, (2017, 2019))

    def test_idempotent_and_order_independent(self):
        first = changes(self.wide)
        second = changes(self.wide.sample(frac=1, random_state=2))
        np.testing.assert_allclose(first, second)
        first["reallocation_index"] = first[SHARES].abs().sum(axis=1) / 2
        np.testing.assert_allclose(first, second)

    def test_published_snapshot_headline(self):
        delta = changes(self.wide)
        self.assertAlmostEqual(delta.share_central.mean(), 1.1483288848302275)
        self.assertEqual(int(delta.share_central.gt(0).sum()), 21)
        self.assertEqual(int(self.audit.value.isna().sum()), 240)
        self.assertTrue(self.audit.loc[self.audit.value.isna(), "value"].isna().all())


if __name__ == "__main__":
    unittest.main()
