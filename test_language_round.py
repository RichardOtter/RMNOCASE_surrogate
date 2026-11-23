import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import language_round


class LanguageRoundTests(unittest.TestCase):
    def test_extended_cases_cover_supplementary_cjk_and_script_marks(self):
        cases = language_round.extended_cases()
        ideographs = {
            char
            for group, _, a, b in cases if group == "CJK_SUPPLEMENTARY"
            for char in (a, b)
        }
        self.assertEqual(len(ideographs), 74400)
        self.assertIn(["HEBREW", "unmarked", "\u05b0", ""], cases)
        self.assertIn(["ARABIC", "unmarked", "\u064e", ""], cases)

    def test_round_requires_rebuild_and_preserves_source(self):
        cases = [
            ["LATIN", "example", "Müller", "muller"],
            ["LATIN", "example", "a", "b"],
            ["JAPANESE", "example", "カ", "か"],
        ]
        with tempfile.TemporaryDirectory(dir=language_round.FOLDER) as directory:
            folder = Path(directory)
            source = folder / "source.rmtree"
            database = folder / "work.rmtree"
            plan = folder / "plan.json"
            observations = folder / "observations.json"
            with contextlib.closing(sqlite3.connect(source)) as conn:
                conn.create_collation("RMNOCASE", language_round.rmnocase)
                conn.execute(
                    "CREATE TABLE PlaceTable (PlaceID INTEGER PRIMARY KEY, "
                    "PlaceType INTEGER, Name TEXT COLLATE RMNOCASE, Abbrev TEXT, "
                    "Normalized TEXT, Latitude INTEGER, Longitude INTEGER, "
                    "LatLongExact INTEGER, MasterID INTEGER, Note TEXT, "
                    "Reverse TEXT COLLATE RMNOCASE, fsID INTEGER, anID INTEGER, "
                    "UTCModDate FLOAT)"
                )
                conn.execute("CREATE INDEX idxPlaceName ON PlaceTable(Name)")
                conn.commit()
            original = source.read_bytes()
            paths = {"database": database, "plan_path": plan, "observations_path": observations}
            with contextlib.redirect_stdout(io.StringIO()):
                language_round.prepare(cases, source=source, **paths)
                with self.assertRaisesRegex(RuntimeError, "rebuild indexes"):
                    language_round.analyze(**paths)
                with contextlib.closing(sqlite3.connect(database)) as conn:
                    conn.create_collation("RMNOCASE", language_round.rmnocase)
                    conn.execute("REINDEX RMNOCASE")
                    conn.commit()
                language_round.analyze(**paths)
                with observations.open(encoding="utf-8") as file:
                    pairs = json.load(file)["pairs"]
                self.assertEqual([pair[-1] for pair in pairs], [0, -1, 1])
                with self.assertRaises(FileExistsError):
                    language_round.prepare(cases, source=source, **paths)
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
