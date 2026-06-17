from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.app.gpkg import projection_string_from_map_info
from gpkg_fixture import build_test_gpkg
from test_backend import PROJECTION


class GpkgProjectionTests(unittest.TestCase):
    def test_projection_can_load_from_gpkg_spatial_ref_sys(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gpkg-projection-test-") as temp_dir:
            gpkg_path = Path(temp_dir) / "demo.gpkg"
            build_test_gpkg(gpkg_path, PROJECTION)
            with sqlite3.connect(gpkg_path) as connection:
                connection.execute("DROP TABLE MapInfo")

            self.assertEqual(projection_string_from_map_info(gpkg_path), PROJECTION)


if __name__ == "__main__":
    unittest.main()
