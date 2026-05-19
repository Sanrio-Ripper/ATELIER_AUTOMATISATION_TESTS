"""
Runner de tests pour l'API ipify.
Exécute la suite de tests, mesure la QoS, et stocke les résultats en SQLite.
"""

import json
import os
import re
import sqlite3
import statistics
import time
from datetime import datetime

import requests


API_URL = "https://api.ipify.org?format=json"
API_URL_TEXT = "https://api.ipify.org?format=text"
TIMEOUT = 3
MAX_RETRIES = 1
N_LATENCY_CALLS = 10

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "runs.db")


def init_db():
    """Crée le dossier db et la table runs si nécessaire."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            api TEXT NOT NULL,
            passed INTEGER NOT NULL,
            failed INTEGER NOT NULL,
            error_rate REAL NOT NULL,
            latency_avg REAL NOT NULL,
            latency_p95 REAL NOT NULL,
            details TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def http_get(url, timeout=TIMEOUT, max_retries=MAX_RETRIES):
    """Wrapper avec timeout + retry simple + backoff sur 429."""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 429:
                # Rate limit : backoff exponentiel
                time.sleep(2 ** attempt)
                continue
            return r
        except requests.Timeout as e:
            last_err = e
            time.sleep(0.5)
        except requests.RequestException as e:
            last_err = e
            break
    if last_err:
        raise last_err
    return None


# ---- Tests individuels ----

def test_status_200():
    r = http_get(API_URL)
    assert r.status_code == 200, f"Status {r.status_code} au lieu de 200"
    return {"name": "status_200", "status": "PASS"}


def test_content_type_json():
    r = http_get(API_URL)
    ct = r.headers.get("Content-Type", "")
    assert "application/json" in ct, f"Content-Type={ct}"
    return {"name": "content_type_json", "status": "PASS"}


def test_field_ip_present():
    r = http_get(API_URL)
    data = r.json()
    assert "ip" in data, f"Champ 'ip' manquant : {data}"
    return {"name": "field_ip_present", "status": "PASS"}


def test_ip_is_string():
    r = http_get(API_URL)
    data = r.json()
    assert isinstance(data["ip"], str), f"Type {type(data['ip'])} au lieu de str"
    return {"name": "ip_is_string", "status": "PASS"}


def test_ip_valid_format():
    r = http_get(API_URL)
    data = r.json()
    ip = data["ip"]
    ipv4 = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
    ipv6 = re.compile(r"^[0-9a-fA-F:]+$")
    assert ipv4.match(ip) or ipv6.match(ip), f"IP invalide : {ip}"
    return {"name": "ip_valid_format", "status": "PASS"}


def test_text_endpoint():
    r = http_get(API_URL_TEXT)
    body = r.text.strip()
    # Doit être du texte brut (pas du JSON)
    assert not body.startswith("{"), f"Réponse JSON au lieu de texte : {body[:50]}"
    ipv4 = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
    ipv6 = re.compile(r"^[0-9a-fA-F:]+$")
    assert ipv4.match(body) or ipv6.match(body), f"Pas une IP valide : {body[:50]}"
    return {"name": "text_endpoint", "status": "PASS"}


TESTS = [
    test_status_200,
    test_content_type_json,
    test_field_ip_present,
    test_ip_is_string,
    test_ip_valid_format,
    test_text_endpoint,
]


def measure_latency():
    """Lance N appels pour mesurer la latence."""
    latencies = []
    for _ in range(N_LATENCY_CALLS):
        t0 = time.perf_counter()
        try:
            http_get(API_URL)
            latencies.append((time.perf_counter() - t0) * 1000)
        except Exception:
            pass
        time.sleep(0.1)  # éviter de spammer
    if not latencies:
        return 0, 0
    avg = round(statistics.mean(latencies), 1)
    # p95
    sorted_l = sorted(latencies)
    idx = max(0, int(len(sorted_l) * 0.95) - 1)
    p95 = round(sorted_l[idx], 1)
    return avg, p95


def run_all():
    """Exécute tous les tests, mesure la QoS, stocke en BDD."""
    init_db()
    details = []
    passed = 0
    failed = 0

    for test_fn in TESTS:
        t0 = time.perf_counter()
        try:
            result = test_fn()
            result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            details.append(result)
            passed += 1
        except AssertionError as e:
            details.append({
                "name": test_fn.__name__.replace("test_", ""),
                "status": "FAIL",
                "details": str(e),
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)
            })
            failed += 1
        except Exception as e:
            details.append({
                "name": test_fn.__name__.replace("test_", ""),
                "status": "ERROR",
                "details": f"{type(e).__name__}: {e}",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1)
            })
            failed += 1

    total = passed + failed
    error_rate = round(failed / total, 3) if total else 0
    latency_avg, latency_p95 = measure_latency()

    # Stockage en SQLite
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO runs (timestamp, api, passed, failed, error_rate, latency_avg, latency_p95, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(timespec="seconds"),
        "ipify",
        passed,
        failed,
        error_rate,
        latency_avg,
        latency_p95,
        json.dumps(details, ensure_ascii=False)
    ))
    conn.commit()
    conn.close()

    print(f"[{datetime.now().isoformat(timespec='seconds')}] "
          f"PASS={passed} FAIL={failed} error_rate={error_rate} "
          f"latency_avg={latency_avg}ms p95={latency_p95}ms")

    return {
        "passed": passed,
        "failed": failed,
        "error_rate": error_rate,
        "latency_avg": latency_avg,
        "latency_p95": latency_p95,
        "details": details
    }


if __name__ == "__main__":
    run_all()
