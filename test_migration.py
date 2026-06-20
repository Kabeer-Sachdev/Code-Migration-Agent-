#!/usr/bin/env python
"""Test migration backend - integration test."""
import os
import sys
import time
import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000")
API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

files = {"files": ("Program.cs", open("sample-dotnet-profile/Program.cs").read())}
data = {"api_key": API_KEY, "model": MODEL}

print(f"Testing migration at {API_URL}")
resp = httpx.post(f"{API_URL}/api/migrate", files=files, data=data, timeout=30)
result = resp.json()
job_id = result.get("job_id")
print(f"Job created: {job_id}")

print("Waiting for processing...")
for _ in range(12):
    time.sleep(5)
    r = httpx.get(f"{API_URL}/api/migrate/{job_id}/status", timeout=10).json()
    status = r.get("status")
    progress = r.get("progress", 0)
    print(f"  Status: {status} ({progress}%)")
    if status in ("complete", "error"):
        break

r = httpx.get(f"{API_URL}/api/migrate/{job_id}", timeout=10).json()
print(f"\nFinal Status: {r.get('status')}")
print(f"Java Files: {len(r.get('java_files', []))}")
print(f"Test Files: {len(r.get('test_files', []))}")

if r.get("error"):
    print(f"\nError: {r['error'][:500]}")
    sys.exit(1)

if r.get("java_files"):
    print("\nSUCCESS - Migration working!")
    for jf in r["java_files"]:
        print(f"  Generated: {jf['filename']} ({len(jf['content'])} chars)")
else:
    print("\nWARNING - No Java files generated")
