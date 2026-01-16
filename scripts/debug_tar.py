import sys
import tarfile

try:
    with tarfile.open(sys.argv[1], "r:gz") as tar:
        for member in tar.getmembers():
            print(f"{member.name} - {member.size} bytes")
except Exception as e:
    print(f"Error: {e}")
