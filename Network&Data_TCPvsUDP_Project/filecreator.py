import os

# create folder
os.makedirs("test_files/test_100kb.dat", exist_ok=True)

files = {
    "test_100kb.dat": 102400,
    "test_1mb.dat": 1048576,
    "test_5mb.dat": 5242880
}

for name, size in files.items():
    with open(f"test_files/{name}", "wb") as f:
        f.write(b"0" * size)

print("✅ test_files created successfully")