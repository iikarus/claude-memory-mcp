import argparse
import datetime
import os
import subprocess
from typing import Optional

BACKUP_DIR = "backups"


def backup(tag: Optional[str] = None) -> None:
    if not tag:
        tag = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    target_dir = os.path.join(BACKUP_DIR, tag)
    os.makedirs(target_dir, exist_ok=True)

    print(f"💾 Creating Save Point: {tag}")

    # 0. Sync to Disk
    _trigger_persistence()

    # Check execution environment (Container vs Host)
    # If we are in the dashboard container, we have direct read-only access to data via /mnt
    falkor_mount = "/mnt/falkor_data"
    qdrant_mount = "/mnt/qdrant_data"
    in_container = os.path.exists(falkor_mount) and os.path.exists(qdrant_mount)

    # 1. Backup FalkorDB
    print("   Backing up FalkorDB...", end=" ", flush=True)
    falkor_archive = os.path.join(target_dir, "falkor_data.tar.gz")

    if in_container:
        # Direct Tar
        cmd_falkor = ["tar", "czf", falkor_archive, "-C", falkor_mount, "."]
    else:
        # Docker Run (Host Mode)
        project_name = "claude-memory-mcp"
        falkor_vol = f"{project_name}_falkordb_data"

        # Resolve absolute path for Host volume mount
        host_target_dir = os.path.abspath(target_dir)

        cmd_falkor = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{falkor_vol}:/data",
            "-v",
            f"{host_target_dir}:/backup",
            "alpine",
            "tar",
            "czf",
            "/backup/falkor_data.tar.gz",
            "-C",
            "/data",
            ".",
        ]

    res = subprocess.run(cmd_falkor, capture_output=True)
    if res.returncode == 0:
        print("✅")
    else:
        print("❌")
        print(res.stderr.decode("utf-8"))

    # 2. Backup Qdrant
    print("   Backing up Qdrant...", end=" ", flush=True)
    qdrant_archive = os.path.join(target_dir, "qdrant_data.tar.gz")

    if in_container:
        # Direct Tar
        cmd_qdrant = ["tar", "czf", qdrant_archive, "-C", qdrant_mount, "."]
    else:
        # Docker Run (Host Mode)
        project_name = "claude-memory-mcp"
        qdrant_vol = f"{project_name}_qdrant_data"
        host_target_dir = os.path.abspath(target_dir)

        cmd_qdrant = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{qdrant_vol}:/qdrant/storage",
            "-v",
            f"{host_target_dir}:/backup",
            "alpine",
            "tar",
            "czf",
            "/backup/qdrant_data.tar.gz",
            "-C",
            "/qdrant/storage",
            ".",
        ]

    res = subprocess.run(cmd_qdrant, capture_output=True)
    if res.returncode == 0:
        print("✅")
    else:
        print("❌")
        print(res.stderr.decode("utf-8"))

    print(f"✨ Save Point Created in {target_dir}")
    _verify_backup(target_dir)


def _trigger_persistence() -> None:
    """Forces databases to flush to disk before backup."""
    # 1. FalkorDB (Redis)
    try:
        host = os.getenv("FALKORDB_HOST", "localhost")
        port = int(os.getenv("FALKORDB_PORT", 6379))
        import redis

        r = redis.Redis(host=host, port=port)
        r.save()  # Synchronous save
        print("💾 FalkorDB Saved to Disk.")
    except Exception:
        print("⚠️ Could not trigger FalkorDB SAVE. Proceeding anyway.")


def _verify_backup(target_dir: str) -> None:
    """Checks if backup files are valid (non-empty)."""
    min_size = 1024 * 10  # 10KB minimum

    for filename in ["falkor_data.tar.gz", "qdrant_data.tar.gz"]:
        path = os.path.join(target_dir, filename)
        if not os.path.exists(path):
            print(f"❌ ERROR: Missing backup file {filename}")
            continue

        size = os.path.getsize(path)
        if size < min_size:
            print(
                f"⚠️  WARNING: {filename} is suspiciously small ({size} bytes). Backup might be empty."
            )
        else:
            print(f"✅ Verified {filename} ({size / 1024:.2f} KB)")


def restore(tag: str, force: bool = False) -> None:
    target_dir = os.path.join(BACKUP_DIR, tag)
    if not os.path.exists(target_dir):
        print(f"❌ Backup '{tag}' not found in {BACKUP_DIR}")
        return

    print(f"♻️  Restoring Save Point: {tag}")
    print("⚠️  WARNING: This will overwrite current database state.")

    if not force:
        confirm = input("Type 'RESTORE' to confirm: ")
        if confirm != "RESTORE":
            print("Aborted.")
            return
    else:
        print("Force mode enabled. Proceeding immediately.")

    # Stop containers first to avoid corruption
    print("Stopping containers...")
    subprocess.run(["docker-compose", "stop"])

    # Restore FalkorDB
    project_name = "claude-memory-mcp"
    falkor_vol = f"{project_name}_falkordb_data"
    qdrant_vol = f"{project_name}_qdrant_data"

    print("Restoring FalkorDB...", end=" ")
    cmd_falkor = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{falkor_vol}:/data",
        "-v",
        f"{os.path.abspath(target_dir)}:/backup",
        "alpine",
        "sh",
        "-c",
        "rm -rf /data/* && tar xzf /backup/falkor_data.tar.gz -C /data",
    ]
    subprocess.run(cmd_falkor)
    print("✅")

    # Restore Qdrant
    print("Restoring Qdrant...", end=" ")
    cmd_qdrant = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{qdrant_vol}:/qdrant/storage",
        "-v",
        f"{os.path.abspath(target_dir)}:/backup",
        "alpine",
        "sh",
        "-c",
        "rm -rf /qdrant/storage/* && tar xzf /backup/qdrant_data.tar.gz -C /qdrant/storage",
    ]
    subprocess.run(cmd_qdrant)
    print("✅")

    print("Restarting containers...")
    subprocess.run(["docker-compose", "up", "-d"])
    print("✨ System Restored.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup/Restore Exocortex Memory")
    subparsers = parser.add_subparsers(dest="command")

    p_backup = subparsers.add_parser("save", help="Create a backup snapshot")
    p_backup.add_argument("--tag", help="Custom name for the backup")  # e.g. "pre_upgrade"

    p_restore = subparsers.add_parser("load", help="Restore a backup snapshot")
    p_restore.add_argument("tag", help="Name of the backup to restore")
    p_restore.add_argument("--force", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    if args.command == "save":
        backup(args.tag)
    elif args.command == "load":
        restore(args.tag, args.force)
    else:
        parser.print_help()
