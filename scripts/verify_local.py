"""Verifica a API em um PostgreSQL descartável, sem Docker e sem tocar outros bancos."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4
import time
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--postgres-bin", type=Path, required=True)
    parser.add_argument("tests", nargs="*", default=["tests"])
    args = parser.parse_args()
    local = ROOT / ".local"
    local.mkdir(exist_ok=True)
    run = local / ("verification-" + uuid4().hex[:12])
    run.mkdir()
    data = run / "postgres"
    ports = set()
    while len(ports) < 3:
        ports.add(free_port())
    db_port, api_port, registry_port = ports
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", APP_ENV="test",
               INTERNAL_TOKEN="verification-only-token", SERVER_LOCALHOST="127.0.0.1",
               API_PORT=str(api_port), API_BASE_URL=f"http://127.0.0.1:{api_port}",
               ALLOW_TEST_DATABASE_RESET="1",
               MOCKSERVER_URL=f"http://127.0.0.1:{registry_port}",
               BET_REGISTRY_URL=f"http://127.0.0.1:{registry_port}/bets.csv",
               DATABASE_URL=f"postgresql+psycopg2://bootcamp@127.0.0.1:{db_port}/bootcamp_test")
    env["TEMP"] = env["TMP"] = str(run)
    env["PYTHONPYCACHEPREFIX"] = str(run / "bytecode")
    postgres = args.postgres_bin.resolve()

    def execute(command, **kwargs):
        with (run / "setup.log").open("a", encoding="utf-8") as log:
            result = subprocess.run([str(item) for item in command], cwd=ROOT, env=env,
                                    creationflags=NO_WINDOW, stdout=log, stderr=subprocess.STDOUT, **kwargs)
        if result.returncode:
            print((run / "setup.log").read_text(encoding="utf-8", errors="replace"), flush=True)
            result.check_returncode()
        return result

    api = None
    sys.path.insert(0, str(ROOT))
    from tests.mock_registry_server import start_registry_server
    registry_server = start_registry_server(registry_port)
    started = False
    print(f"Verification artifacts: {run}", flush=True)
    try:
        execute([postgres / "initdb", "-D", data, "-U", "bootcamp", "-A", "trust", "--encoding=UTF8", "--locale=C"])
        execute([postgres / "pg_ctl", "-D", data, "-l", run / "postgres.log",
                 "-o", f"-h 127.0.0.1 -p {db_port}", "-w", "start"])
        started = True
        execute([postgres / "createdb", "-h", "127.0.0.1", "-p", db_port, "-U", "bootcamp", "bootcamp_test"])
        execute([postgres / "psql", "-h", "127.0.0.1", "-p", db_port, "-U", "bootcamp", "-d", "bootcamp_test",
                 "-v", "ON_ERROR_STOP=1", "-f", ROOT / "database/database.sql"])
        with (run / "api.log").open("w", encoding="utf-8") as log:
            api = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "app:app",
                                    "--host", "127.0.0.1", "--port", str(api_port), "--no-access-log"],
                                   cwd=ROOT / "src", env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=NO_WINDOW)
            for attempt in range(120):
                if api.poll() is not None:
                    raise RuntimeError("API exited; inspect api.log.")
                try:
                    with urlopen(env["API_BASE_URL"] + "/health_check", timeout=1) as response:
                        if response.status in (200, 204):
                            break
                except OSError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("API readiness timeout.")
            with (run / "pytest.log").open("w", encoding="utf-8") as test_log:
                result = subprocess.run([sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider",
                                         "--basetemp", str(run / "pytest"), "--junitxml", str(run / "results.xml"),
                                         "-q", *args.tests], cwd=ROOT, env=env, creationflags=NO_WINDOW,
                                        stdout=test_log, stderr=subprocess.STDOUT)
            print((run / "pytest.log").read_text(encoding="utf-8"), flush=True)
            return result.returncode
    finally:
        registry_server.shutdown()
        registry_server.server_close()
        if api is not None and api.poll() is None:
            api.terminate()
            try:
                api.wait(timeout=15)
            except subprocess.TimeoutExpired:
                api.kill()
                api.wait()
        if started:
            execute([postgres / "pg_ctl", "-D", data, "-m", "fast", "-w", "stop"])


if __name__ == "__main__":
    sys.exit(main())
