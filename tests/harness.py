"""시험이 함께 쓰는 것들 — 브라우저 자리, 주소, 임시 폴더, 서버.

시험마다 크로미움 경로와 포트를 적어 두면 기계가 바뀔 때마다 전부 고쳐야 한다.
여기 한 곳에서만 정한다. 값은 환경변수로 덮어쓸 수 있어, 다른 기기에서도
`GIJUL_CHROME=... python3 tests/run.py` 로 돌릴 수 있다.
"""
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _chrome():
    """플레이라이트가 받아 둔 크로미움을 찾는다. 판마다 폴더 이름이 달라 훑는다."""
    env = os.environ.get("GIJUL_CHROME")
    if env:
        return env
    for base in (os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers",
                 str(Path.home() / ".cache/ms-playwright")):
        found = sorted(Path(base).glob("chromium*/chrome-linux/chrome")) if Path(base).is_dir() else []
        if found:
            return str(found[-1])
    return shutil.which("chromium") or shutil.which("google-chrome") or "chromium"


CHROME = _chrome()

# run.py 가 서버를 띄우고 여기에 주소를 넣어 준다. 혼자 돌릴 때는 스스로 띄운다.
URL = os.environ.get("GIJUL_URL", "")

# 스크린샷처럼 남기는 것은 저장소를 어지럽히지 않도록 임시 폴더로 보낸다.
SHOT = Path(os.environ.get("GIJUL_SHOT") or tempfile.mkdtemp(prefix="gijul-shot-"))


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Serve:
    """저장소(또는 그 사본)를 정적으로 내주는 서버.

    사본을 쓰는 시험이 있다 — 서비스 워커가 셸이 바뀐 것을 알아채는지 보려면
    돌아가는 도중에 파일을 고쳐야 하는데, 저장소를 직접 고칠 수는 없다.
    """

    def __init__(self, copy=False):
        self.copy = copy
        self.dir = None
        self.proc = None

    def __enter__(self):
        if self.copy:
            self.dir = Path(tempfile.mkdtemp(prefix="gijul-site-"))
            shutil.rmtree(self.dir)
            shutil.copytree(ROOT, self.dir, ignore=shutil.ignore_patterns(".git", "tests"))
        else:
            self.dir = ROOT
        port = free_port()
        self.proc = subprocess.Popen(
            ["python3", "-m", "http.server", str(port)], cwd=self.dir,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.url = f"http://127.0.0.1:{port}/"
        for _ in range(80):                      # 뜰 때까지 기다린다
            try:
                with socket.create_connection(("127.0.0.1", port), 0.2):
                    break
            except OSError:
                time.sleep(0.05)
        return self

    def __exit__(self, *a):
        if self.proc:
            self.proc.terminate()
        if self.copy and self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)
        return False


def site():
    """이 시험이 볼 주소. run.py 가 띄워 둔 것이 있으면 그것을 쓴다."""
    if URL:
        return None, URL
    s = Serve().__enter__()
    return s, s.url
