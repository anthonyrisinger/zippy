import unittest

class PythonTest(unittest.TestCase):
    def test_version(self):
        import sys
        self.assertEqual((2, 7, 6, 'final', 0), sys.version_info)

