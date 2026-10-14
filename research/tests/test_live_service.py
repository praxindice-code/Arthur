"""Exercise the shipped Rust/Zig live binary over loopback HTTP."""
import os
from pathlib import Path
import socket
import subprocess
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "bin" / "bayesguard-live.exe"


@unittest.skipUnless(EXE.exists(), "build-native.ps1 has not built live binary")
class LiveServiceTests(unittest.TestCase):
    def setUp(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        self.key = "local-integration-test-key"
        env = os.environ.copy()
        env["BAYESGUARD_KEY"] = self.key
        env["BAYESGUARD_BIND"] = f"127.0.0.1:{port}"
        self.process = subprocess.Popen([str(EXE)], env=env,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                with urlopen(self.url + "/health", timeout=.2) as result:
                    if result.read() == b"ok\n":
                        break
            except (URLError, TimeoutError):
                time.sleep(.02)
        else:
            self.tearDown()
            self.fail("live service did not start")

    def tearDown(self):
        if hasattr(self, "process") and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)

    def request(self, path, body=None, key=None):
        headers = {"x-api-key": key or self.key}
        if body is not None:
            headers["Content-Type"] = "text/plain"
        request = Request(self.url + path, data=body, headers=headers,
                          method="POST" if body is not None else "GET")
        with urlopen(request, timeout=5) as result:
            return result.read().decode("utf-8")

    def test_scoring_replay_alerts_and_auth(self):
        body = b"test-session\t0\taction_ok\ntest-session\t1\treward_mismatch\n"
        first = self.request("/v1/events", body)
        self.assertEqual(first, self.request("/v1/events", body))
        self.assertEqual(len(first.splitlines()), 2)
        next_body = "".join(
            f"test-session\t{step}\treward_mismatch\n" for step in range(2, 12)
        ).encode("utf-8")
        self.request("/v1/events", next_body)
        alerts = self.request("/v1/alerts")
        self.assertIn("test-session", alerts)
        self.assertEqual(len(alerts.splitlines()[0].split("\t")), 7)
        with self.assertRaises(HTTPError) as bad_key:
            self.request("/v1/alerts", key="wrong-key")
        self.assertEqual(bad_key.exception.code, 401)
        with self.assertRaises(HTTPError) as conflict:
            self.request("/v1/events", b"test-session\t1\taction_ok\n")
        self.assertEqual(conflict.exception.code, 400)
