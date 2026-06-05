#!/usr/bin/env python3
"""
Bank Transaction Producer — local JSONL generator (free to run).

Changes vs the original:
- Landing files are bucketed by INGESTION date (UTC) only, e.g. <OUTPUT_DIR>/2026-06-05/.
  This is for housekeeping (S3 lifecycle / smaller prefixes), NOT a query partition —
  the downstream Iceberg table owns query partitioning on event_time.
- Filenames are globally unique and sortable (UTC timestamp + short uuid), so they can
  serve as a stable dedup identity for the ingestion job and never collide across
  concurrent producers / CI runners.
- All timestamps use UTC.
- Buffered flushing (every N records or every few seconds) instead of flushing on every
  record, for much higher throughput. A graceful stop still flushes via file close().
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from config.config import Config
from .transaction_generator import TransactionGenerator


class TransactionProducer:
    """Transaction producer — writes JSONL directly to local files."""

    def __init__(self, config: Config):
        self.config = config
        self.generator = TransactionGenerator()

        # statistics
        self.total_sent = 0
        self.start_time = None

        # output file handle and path
        self.current_file = None
        self.current_file_path = None
        self.current_file_size = 0
        self.last_rotate_time = None

        # flush policy: bound the data-loss window on a hard crash without
        # paying a flush() syscall on every single record.
        # Optional Config knobs (sensible defaults if absent).
        self.flush_every = getattr(config, "FLUSH_EVERY", 200)              # records
        self.flush_interval = getattr(config, "FLUSH_INTERVAL_SECONDS", 1.0)  # seconds
        self._records_since_flush = 0
        self._last_flush_time = time.time()

        # Ensure output directory exists
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        # Open the first file
        self._open_new_file()

    def _get_landing_path(self) -> str:
        """Landing folder bucketed by INGESTION date (UTC) — housekeeping only,
        NOT a query partition (the Iceberg table partitions on event_time)."""
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return os.path.join(self.config.OUTPUT_DIR, day)

    def _get_file_name(self) -> str:
        """Globally-unique, sortable filename. This name (its S3 key downstream)
        is the dedup identity used by the ingestion job; the uuid suffix prevents
        collisions across concurrent producers / CI runners."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"transactions_{ts}_{uuid4().hex[:8]}.jsonl"

    def _open_new_file(self):
        """Close the current file (if any) and open a fresh one."""
        if self.current_file:
            self.current_file.close()  # close() flushes any remaining buffer
            print(f"   Closed: {self.current_file_path}")

        landing_path = self._get_landing_path()
        os.makedirs(landing_path, exist_ok=True)

        file_name = self._get_file_name()
        self.current_file_path = os.path.join(landing_path, file_name)
        self.current_file = open(self.current_file_path, "a", encoding="utf-8")
        self.current_file_size = 0
        self.last_rotate_time = time.time()
        self._records_since_flush = 0
        self._last_flush_time = time.time()

        print(f"📁 New file: {self.current_file_path}")

    def _should_rotate(self) -> bool:
        """Rotate on time threshold, size threshold, or date (UTC) rollover."""
        # time threshold
        if time.time() - self.last_rotate_time >= self.config.ROTATE_SECONDS:
            return True
        # size threshold
        if self.current_file_size >= self.config.ROTATE_SIZE_MB * 1024 * 1024:
            return True
        # date rollover (landing folder changed)
        if self._get_landing_path() != os.path.dirname(self.current_file_path):
            return True
        return False

    def _maybe_flush(self, force: bool = False):
        """Flush periodically (by record count or elapsed time) rather than per record."""
        now = time.time()
        if (
            force
            or self._records_since_flush >= self.flush_every
            or (now - self._last_flush_time) >= self.flush_interval
        ):
            self.current_file.flush()
            self._records_since_flush = 0
            self._last_flush_time = now

    def _write_transaction(self, transaction) -> bool:
        """Write a single transaction as one JSON line."""
        try:
            if self._should_rotate():
                self._open_new_file()

            line = transaction.to_json() + "\n"
            self.current_file.write(line)

            self.current_file_size += len(line.encode("utf-8"))
            self.total_sent += 1
            self._records_since_flush += 1
            self._maybe_flush()

            return True
        except Exception as e:
            print(f"❌ Write error: {e}")
            return False

    def run(self, duration_seconds: Optional[int] = None):
        """Run the producer.

        Args:
            duration_seconds: how long to run (seconds); None runs until Ctrl+C.
        """
        self.start_time = time.time()
        target_tps = self.config.TARGET_TPS

        print("=" * 60)
        print("🏦 Bank Transaction Log Producer")
        print("=" * 60)
        print(f"   Target TPS : {target_tps} rec/s")
        print(f"   Output dir : {self.config.OUTPUT_DIR}")
        print(f"   Rotate by  : {self.config.ROTATE_SECONDS}s or {self.config.ROTATE_SIZE_MB}MB")
        print(f"   Flush every: {self.flush_every} rec or {self.flush_interval}s")
        print("=" * 60)
        print()

        last_report_time = time.time()
        last_report_count = 0

        try:
            while True:
                if duration_seconds and (time.time() - self.start_time) > duration_seconds:
                    break

                transaction = self.generator.generate_transaction()
                self._write_transaction(transaction)

                # cumulative rate control: keep actual throughput near target_tps
                elapsed = time.time() - self.start_time
                expected = self.total_sent / target_tps
                if elapsed < expected:
                    time.sleep(expected - elapsed)

                # rate report once per second
                now = time.time()
                if now - last_report_time >= 1.0:
                    actual_rate = (self.total_sent - last_report_count) / (now - last_report_time)
                    print(
                        f"📊 Rate: {actual_rate:.1f} rec/s | Total: {self.total_sent} | "
                        f"File: {os.path.basename(self.current_file_path)} | "
                        f"Size: {self.current_file_size / 1024 / 1024:.1f}MB"
                    )
                    last_report_time = now
                    last_report_count = self.total_sent

        except KeyboardInterrupt:
            print("\n⏹️  Stopping producer...")
        finally:
            # close() flushes any buffered records, so a graceful stop never loses data
            if self.current_file:
                self.current_file.close()

            elapsed = time.time() - self.start_time if self.start_time else 0
            avg_rate = self.total_sent / elapsed if elapsed > 0 else 0

            print("\n" + "=" * 60)
            print("📈 Final Statistics")
            print("=" * 60)
            print(f"   Total records : {self.total_sent}")
            print(f"   Runtime       : {elapsed:.1f} seconds")
            print(f"   Average rate  : {avg_rate:.1f} rec/s")
            print(f"   Output dir    : {self.config.OUTPUT_DIR}")
            print("=" * 60)

            self._list_output_files()

    def _list_output_files(self):
        """List generated files (first 10 per folder)."""
        print("\n📁 Generated files:")
        for root, dirs, files in os.walk(self.config.OUTPUT_DIR):
            level = root.replace(self.config.OUTPUT_DIR, "").count(os.sep)
            indent = " " * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 2 * (level + 1)
            for file in sorted(files)[:10]:  # only show the first 10
                filepath = os.path.join(root, file)
                size = os.path.getsize(filepath)
                print(f"{subindent}{file} ({size / 1024:.1f}KB)")
            if len(files) > 10:
                print(f"{subindent}... and {len(files) - 10} more")


def main():
    config = Config()

    try:
        config.validate()
    except AssertionError as e:
        print(f"❌ Configuration error: {e}")
        return

    producer = TransactionProducer(config)
    producer.run(duration_seconds=Config.DURATION_SECONDS if Config.DURATION_SECONDS > 0 else None)


if __name__ == "__main__":
    main()