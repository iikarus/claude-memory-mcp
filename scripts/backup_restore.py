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

    # 1. Backup FalkorDB Volume
    print("   Backing up FalkorDB...", end=" ", flush=True)
    # We use a helper container to mount the volume and tar it to host
    # Assuming volume name 'claude-memory-mcp_falkordb_data' (standard compose name)
    # Correct method: use docker run --rm -v vol:/data -v host:/backup ubuntu tar ...

    # First, identify volumes (Compose usually prefixes with project name)
    project_name = "claude-memory-mcp"
    falkor_vol = f"{project_name}_falkordb_data"
    qdrant_vol = f"{project_name}_qdrant_data"

    cmd_falkor = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{falkor_vol}:/data",
        "-v",
        f"{os.path.abspath(target_dir)}:/backup",
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

    # 2. Backup Qdrant Volume
    print("   Backing up Qdrant...", end=" ", flush=True)
    cmd_qdrant = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{qdrant_vol}:/qdrant/storage",
        "-v",
        f"{os.path.abspath(target_dir)}:/backup",
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


def restore(tag: str) -> None:
    target_dir = os.path.join(BACKUP_DIR, tag)
    if not os.path.exists(target_dir):
        print(f"❌ Backup '{tag}' not found in {BACKUP_DIR}")
        return

    print(f"♻️  Restoring Save Point: {tag}")
    print("⚠️  WARNING: This will overwrite current database state.")
    confirm = input("Type 'RESTORE' to confirm: ")
    if confirm != "RESTORE":
        print("Aborted.")
        return

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

    args = parser.parse_args()

    if args.command == "save":
        backup(args.tag)
    elif args.command == "load":
        restore(args.tag)
    else:
        parser.print_help()
