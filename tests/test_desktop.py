import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import desktop


class DesktopTests(unittest.TestCase):
    def test_user_data_is_outside_installation(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": "C:/Users/Cliente/AppData/Local"}):
            with patch.object(sys, "platform", "win32"):
                with patch.dict(os.environ):
                    os.environ.pop("DOCE_ATELIE_HOME", None)
                    self.assertEqual(desktop.user_root(), Path("C:/Users/Cliente/AppData/Local/DoceAtelie"))

    def test_data_override(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"DOCE_ATELIE_HOME": temp}):
                root = desktop.prepare_data()
                self.assertTrue((root / "dados").is_dir())
                self.assertTrue((root / "midia").is_dir())
                self.assertEqual(os.environ["CONFEITARIA_DATA_DIR"], str(root / "dados"))

    def test_lock_prevents_second_instance(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "app.lock"
            first, second = desktop.InstanceLock(path), desktop.InstanceLock(path)
            self.assertTrue(first.acquire())
            try:
                code = "from pathlib import Path; from desktop import InstanceLock; import sys; lock=InstanceLock(Path(sys.argv[1])); sys.exit(1 if lock.acquire() else 0)"
                result = subprocess.run([sys.executable, "-c", code, str(path)], cwd=Path(__file__).resolve().parent.parent, timeout=10)
                self.assertEqual(result.returncode, 0)
            finally:
                first.release()
            self.assertTrue(second.acquire())
            second.release()

    def test_source_desktop_serves_and_stops(self):
        path = Path(__file__).resolve().parent.parent / "packaging" / "smoke_bundle.py"
        spec = importlib.util.spec_from_file_location("bundle_smoke", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.check_bundle(Path(__file__).resolve().parent.parent / "desktop.py")


if __name__ == "__main__":
    unittest.main()
