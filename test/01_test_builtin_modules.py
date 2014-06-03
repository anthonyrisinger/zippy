import unittest

class BuiltinModuleTest(unittest.TestCase):
    def test_builtin_modules(self):
        import sys
        for module_name in sys.builtin_module_names:
            try:
                test = __import__(module_name)
            except ImportError:
                self.fail("Unable to import %s" % module_name)
