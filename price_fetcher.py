"""
CriptoYa USDC/ARS price fetcher — runs every 10 minutes and stores results in PostgreSQL.

Usage:
    python price_fetcher.py            # runs continuously (every 10 min)
    python price_fetcher.py --once     # single fetch, then exits (good for cron)
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

API_URL = "https://criptoya.com/api/dolarapp/USDC/ARS/1"
INTERVAL_SECONDS = 10 * 60  # 10 minutes
BA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "criptoya"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("price_fetcher.log"),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def ensure_table(conn):
    """Create the prices table if it doesn't exist yet."""
    ddl = """
    CREATE TABLE IF NOT EXISTS public.usdc_ars_prices (
        id          SERIAL PRIMARY KEY,
        fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        total_bid   NUMERIC(18, 6),
        total_ask   NUMERIC(18, 6),
        api_time    TIMESTAMP,
        raw_response JSONB
    );
    """
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    log.info("Table 'usdc_ars_prices' is ready.")


def unix_to_dt(unix_ts):
    """Convert a Unix epoch integer to a Buenos Aires datetime (YYYY/MM/DD HH:MM, no seconds)."""
    if unix_ts is None:
        return None
    dt_utc = datetime.fromtimestamp(int(unix_ts), tz=timezone.utc)
    dt_ba = dt_utc.astimezone(BA_TZ)
    return dt_ba.replace(second=0, microsecond=0, tzinfo=None)



def insert_price(conn, payload: dict):
    sql = """
    INSERT INTO public.usdc_ars_prices (fetched_at, total_bid, total_ask, api_time, raw_response)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id;
    """
    api_dt = unix_to_dt(payload.get("time"))
    with conn.cursor() as cur:
        cur.execute(sql, (
            datetime.now(BA_TZ).replace(second=0, microsecond=0, tzinfo=None),
            payload.get("totalBid"),
            payload.get("totalAsk"),
            api_dt,
            json.dumps(payload),
        ))
        row_id = cur.fetchone()[0]
    conn.commit()
    return row_id


# ---------------------------------------------------------------------------
# Fetch + store
# ---------------------------------------------------------------------------
def fetch_and_store():
    log.info("Fetching %s ...", API_URL)
    try:
        resp = requests.get(API_URL, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        log.info("Response: %s", payload)
    except requests.RequestException as exc:
        log.error("HTTP request failed: %s", exc)
        return

    try:
        conn = get_connection()
        ensure_table(conn)
        row_id = insert_price(conn, payload)
        conn.close()
        log.info("Stored as row id=%d", row_id)
    except psycopg2.Error as exc:
        log.error("Database error: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch once and exit (use this when running via cron)",
    )
    args = parser.parse_args()

    if args.once:
        fetch_and_store()
        return

if __name__ == "__main__":
    main()