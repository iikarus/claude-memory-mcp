"""Scheduled backup script for Exocortex brain data.

Runs daily via Windows Task Scheduler. Creates local backup,
syncs to Google Drive, and enforces rolling 7-day retention.

Usage:
    python scripts/scheduled_backup.py           # run backup + cleanup
    python scripts/scheduled_backup.py --dry-run  # show what would happen
"""

import argparse
import datetime
import logging
import shutil
import subprocess
import sys
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = PROJECT_ROOT / "backups"
GDRIVE_BACKUP_DIR = Path(r"G:\My Drive\exocortex_backups")
RETENTION_DAYS = 7
TAG_PREFIX = "daily_"
LOG_FILE = PROJECT_ROOT / "backups" / "scheduled_backup.log"


def setup_logging() -> logging.Logger:
    """Configure file + console logging."""
    logger = logging.getLogger("scheduled_backup")
    logger.setLevel(logging.INFO)

    # File handler (append)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(ch)

    return logger


def create_backup(tag: str, logger: logging.Logger) -> Path | None:
    """Run backup_restore.py save and return the backup directory."""
    backup_path = BACKUP_DIR / tag
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "backup_restore.py"), "save", "--tag", tag]

    logger.info("Creating backup with tag: %s", tag)
    env = {**__import__("os").environ, "PYTHONUTF8": "1"}
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            timeout=120,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        logger.info("Backup output: %s", result.stdout.strip())
    except subprocess.CalledProcessError as exc:
        logger.error("Backup failed (exit %d): %s", exc.returncode, exc.stderr)
        return None
    except subprocess.TimeoutExpired:
        logger.error("Backup timed out after 120s")
        return None

    if not backup_path.exists():
        logger.error("Backup directory not found: %s", backup_path)
        return None

    return backup_path


def sync_to_gdrive(backup_path: Path, tag: str, logger: logging.Logger) -> bool:
    """Copy backup to Google Drive sync folder."""
    dest = GDRIVE_BACKUP_DIR / tag
    dest.mkdir(parents=True, exist_ok=True)

    logger.info("Syncing to Google Drive: %s", dest)
    try:
        for f in backup_path.iterdir():
            if f.is_file():
                shutil.copy2(f, dest / f.name)
                logger.info("  Copied %s (%.1f KB)", f.name, f.stat().st_size / 1024)
        return True
    except Exception as exc:
        logger.error("Google Drive sync failed: %s", exc)
        return False


def cleanup_old_backups(base_dir: Path, label: str, dry_run: bool, logger: logging.Logger) -> int:
    """Delete daily_* backup dirs older than RETENTION_DAYS. Returns count deleted."""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)
    deleted = 0

    if not base_dir.exists():
        return 0

    for d in sorted(base_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith(TAG_PREFIX):
            continue

        # Parse date from tag: daily_YYYY_MM_DD
        date_str = d.name.replace(TAG_PREFIX, "")
        try:
            backup_date = datetime.datetime.strptime(date_str, "%Y_%m_%d")
        except ValueError:
            continue

        if backup_date < cutoff:
            if dry_run:
                logger.info("[DRY RUN] Would delete %s/%s", label, d.name)
            else:
                shutil.rmtree(d)
                logger.info("Deleted old backup %s/%s", label, d.name)
            deleted += 1

    return deleted


def main() -> None:
    """Entry point for scheduled backup."""
    parser = argparse.ArgumentParser(description="Exocortex scheduled backup")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Scheduled backup started%s", " (DRY RUN)" if args.dry_run else "")

    # Generate tag from today's date
    tag = TAG_PREFIX + datetime.datetime.now().strftime("%Y_%m_%d")

    # Step 1: Create backup
    if args.dry_run:
        logger.info("[DRY RUN] Would create backup: %s", tag)
        backup_path = BACKUP_DIR / tag  # pretend
    else:
        backup_path = create_backup(tag, logger)
        if backup_path is None:
            logger.error("BACKUP FAILED — aborting")
            sys.exit(1)

    # Step 2: Sync to Google Drive
    if args.dry_run:
        logger.info("[DRY RUN] Would sync to %s", GDRIVE_BACKUP_DIR / tag)
    else:
        if not sync_to_gdrive(backup_path, tag, logger):
            logger.warning("Google Drive sync failed — local backup still exists")

    # Step 3: Cleanup old backups (local + Drive)
    local_deleted = cleanup_old_backups(BACKUP_DIR, "local", args.dry_run, logger)
    gdrive_deleted = cleanup_old_backups(GDRIVE_BACKUP_DIR, "gdrive", args.dry_run, logger)

    logger.info(
        "Complete. Cleaned up: %d local, %d gdrive old backups",
        local_deleted,
        gdrive_deleted,
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
