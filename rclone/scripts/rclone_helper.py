#!/usr/bin/env python3
"""
Rclone Helper Script for MinIO Operations

This script provides helper functions for common rclone/MinIO tasks.
"""

import subprocess
import json
import sys
from datetime import datetime, timedelta

def run_command(cmd, capture=True):
    """Execute shell command and return output."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return None
    return result.stdout.strip() if capture else ""

def list_remotes():
    """List all configured rclone remotes."""
    output = run_command(["rclone", "listremotes"])
    if output:
        remotes = [r.rstrip(':') for r in output.split('\n') if r.strip()]
        return remotes
    return []

def list_buckets(remote):
    """List all buckets in a remote."""
    output = run_command(["rclone", "lsd", f"{remote}:"])
    if output:
        buckets = []
        for line in output.split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 5:
                    buckets.append(parts[4])
        return buckets
    return []

def list_files(remote, path=""):
    """List files in a remote path."""
    full_path = f"{remote}:{path}" if path else f"{remote}:"
    output = run_command(["rclone", "lsf", full_path])
    if output:
        files = [f for f in output.split('\n') if f.strip()]
        return files
    return []

def get_file_info(remote, path):
    """Get detailed info about a file."""
    full_path = f"{remote}:{path}"
    output = run_command(["rclone", "info", full_path])
    return output

def upload_file(local_path, remote, remote_path):
    """Upload a file to remote."""
    dest = f"{remote}:{remote_path}"
    return run_command(["rclone", "copy", local_path, dest], capture=False)

def download_file(remote, remote_path, local_path):
    """Download a file from remote."""
    source = f"{remote}:{remote_path}"
    return run_command(["rclone", "copy", source, local_path], capture=False)

def sync_dirs(local_path, remote, remote_path, dry_run=True):
    """Sync local directory to remote."""
    dest = f"{remote}:{remote_path}"
    cmd = ["rclone", "sync", local_path, dest]
    if dry_run:
        cmd.append("--dry-run")
    return run_command(cmd, capture=False)

def move_file(remote, source_path, dest_path):
    """Move a file within remote."""
    src = f"{remote}:{source_path}"
    dst = f"{remote}:{dest_path}"
    return run_command(["rclone", "move", src, dst], capture=False)

def delete_file(remote, path):
    """Delete a file from remote."""
    full_path = f"{remote}:{path}"
    return run_command(["rclone", "delete", full_path], capture=False)

def purge_path(remote, path):
    """Delete all files in a path."""
    full_path = f"{remote}:{path}"
    return run_command(["rclone", "purge", full_path], capture=False)

def get_config(remote=None):
    """Get rclone configuration."""
    if remote:
        return run_command(["rclone", "config", "show", remote])
    return run_command(["rclone", "config", "show"])

def create_bucket(remote, bucket_name):
    """Create a new bucket."""
    return run_command(["rclone", "mkdir", f"{remote}:{bucket_name}"], capture=False)

def delete_bucket(remote, bucket_name):
    """Delete a bucket (must be empty)."""
    return run_command(["rclone", "rmdir", f"{remote}:{bucket_name}"], capture=False)

def main():
    """Main entry point for CLI usage."""
    if len(sys.argv) < 2:
        print("Usage: rclone_helper.py <command> [args...]")
        print("\nCommands:")
        print("  list-remotes           - List all configured remotes")
        print("  list-buckets <remote>  - List buckets in a remote")
        print("  list-files <remote> [path] - List files in remote path")
        print("  info <remote> <path>   - Get file info")
        print("  upload <local> <remote> <path> - Upload file")
        print("  download <remote> <path> <local> - Download file")
        print("  sync <local> <remote> <path> [--dry-run] - Sync directories")
        print("  move <remote> <src> <dst> - Move file")
        print("  delete <remote> <path> - Delete file")
        print("  purge <remote> <path>  - Delete all files in path")
        print("  config [remote]        - Show configuration")
        print("  create-bucket <remote> <name> - Create bucket")
        print("  delete-bucket <remote> <name> - Delete bucket")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list-remotes":
        remotes = list_remotes()
        print("Configured remotes:")
        for r in remotes:
            print(f"  - {r}")

    elif command == "list-buckets":
        if len(sys.argv) < 3:
            print("Error: remote name required")
            sys.exit(1)
        buckets = list_buckets(sys.argv[2])
        print(f"Buckets in {sys.argv[2]}:")
        for b in buckets:
            print(f"  - {b}")

    elif command == "list-files":
        if len(sys.argv) < 3:
            print("Error: remote name required")
            sys.exit(1)
        path = sys.argv[3] if len(sys.argv) > 3 else ""
        files = list_files(sys.argv[2], path)
        print(f"Files in {sys.argv[2]}:{path}:")
        for f in files:
            print(f"  - {f}")

    elif command == "info":
        if len(sys.argv) < 4:
            print("Error: remote and path required")
            sys.exit(1)
        info = get_file_info(sys.argv[2], sys.argv[3])
        print(info)

    elif command == "upload":
        if len(sys.argv) < 5:
            print("Error: local path, remote, and remote path required")
            sys.exit(1)
        upload_file(sys.argv[2], sys.argv[3], sys.argv[4])

    elif command == "download":
        if len(sys.argv) < 5:
            print("Error: remote, remote path, and local path required")
            sys.exit(1)
        download_file(sys.argv[2], sys.argv[3], sys.argv[4])

    elif command == "sync":
        if len(sys.argv) < 5:
            print("Error: local path, remote, and remote path required")
            sys.exit(1)
        dry_run = "--dry-run" in sys.argv
        sync_dirs(sys.argv[2], sys.argv[3], sys.argv[4], dry_run)

    elif command == "move":
        if len(sys.argv) < 5:
            print("Error: remote, source path, and dest path required")
            sys.exit(1)
        move_file(sys.argv[2], sys.argv[3], sys.argv[4])

    elif command == "delete":
        if len(sys.argv) < 4:
            print("Error: remote and path required")
            sys.exit(1)
        delete_file(sys.argv[2], sys.argv[3])

    elif command == "purge":
        if len(sys.argv) < 4:
            print("Error: remote and path required")
            sys.exit(1)
        purge_path(sys.argv[2], sys.argv[3])

    elif command == "config":
        remote = sys.argv[2] if len(sys.argv) > 2 else None
        config = get_config(remote)
        print(config)

    elif command == "create-bucket":
        if len(sys.argv) < 4:
            print("Error: remote and bucket name required")
            sys.exit(1)
        create_bucket(sys.argv[2], sys.argv[3])

    elif command == "delete-bucket":
        if len(sys.argv) < 4:
            print("Error: remote and bucket name required")
            sys.exit(1)
        delete_bucket(sys.argv[2], sys.argv[3])

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
