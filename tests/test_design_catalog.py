import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('design', ROOT / 'site-design' / 'scripts' / 'design.py')
design = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(design)


class DesignCatalogTests(unittest.TestCase):
    def test_serialized_contrast_ratios_have_stable_precision(self):
        data = design.read_catalog()
        result = design.compose(data, next(iter(data['recipes'])))

        for row in result['color_checks']:
            self.assertEqual(row['ratio'], round(row['ratio'], 6))


if __name__ == '__main__':
    unittest.main()
