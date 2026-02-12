---
name: rclone
description: Comprehensive rclone control for MinIO and cloud storage operations. Use when the agent needs to: (1) Manage MinIO buckets and objects, (2) Upload/download/sync files, (3) List and browse cloud storage, (4) Configure rclone remotes including encryption and sharing settings, (5) Generate time-limited share links, (6) Modify bucket permissions and access controls. Supports MinIO, S3, and other rclone-compatible storage backends.
---

# Rclone Control

Control rclone for MinIO and cloud storage operations.

## Quick Start

### Basic Commands

```bash
# List all configured remotes
rclone listremotes

# List files in a remote
rclone ls remote:path
rclone lsf remote:path  # Cleaner output format

# Copy files
rclone copy source destination

# Sync files (destination matches source)
rclone sync source destination

# Move files
rclone move source destination

# Delete files
rclone delete remote:path
rclone purge remote:path  # Delete all files
```

## MinIO Operations

### Bucket Management

```bash
# List all buckets
rclone lsd remote:

# Create a bucket
rclone mkdir remote:bucket-name

# Delete a bucket (must be empty)
rclone rmdir remote:bucket-name

# Check bucket exists
rclone size remote:bucket-name
```

### File Operations

```bash
# Upload files to MinIO
rclone copy local-folder remote:bucket-name/path/

# Download files from MinIO
rclone copy remote:bucket-name/path/ local-folder/

# Sync local folder to MinIO
rclone sync local-folder remote:bucket-name/path/

# Move files within MinIO
rclone move remote:bucket-name/source remote:bucket-name/destination

# Delete specific file
rclone delete remote:bucket-name/path/file.txt

# Delete all files in a path
rclone purge remote:bucket-name/path/
```

### Listing and Browsing

```bash
# List buckets
rclone lsd remote:

# List files with details
rclone ls remote:bucket-name/path/

# List files in cleaner format
rclone lsf remote:bucket-name/path/

# Tree view of directory structure
rclone tree remote:bucket-name/path/

# Get file info
rclone info remote:bucket-name/path/file.txt
```

## Configuration Management

### View Configuration

```bash
# Show current configuration
rclone config show

# Show configuration for specific remote
rclone config show remote-name

# List remotes
rclone listremotes
```

### Configure MinIO Remote

```bash
# Interactive configuration
rclone config

# Non-interactive (example for MinIO)
rclone config create minio-server s3 \
  --s3-provider Minio \
  --s3-endpoint http://localhost:9000 \
  --s3-access-key YOUR_ACCESS_KEY \
  --s3-secret-key YOUR_SECRET_KEY \
  --s3-region us-east-1
```

## Encryption

### Crypt Backend for Server-Side Encryption

```bash
# Create encrypted remote
rclone config create encrypted-minio crypt \
  --crypt-remote minio-server:bucket-name \
  --crypt-password YOUR_PASSWORD

# Use encrypted remote for operations
rclone copy local-file encrypted-minio:path/
```

### Client-Side Encryption

```bash
# Copy to encrypted path
rclone copy local-folder minio-server:encrypted-path/ \
  --crypt-password YOUR_PASSWORD
```

## Share Links

### Generate Time-Limited Share Links

For MinIO, use the built-in share command or MinIO admin tools:

```bash
# Using rclone backend (if supported)
rclone link remote:bucket-name/path/file.txt

# For MinIO-specific sharing, use mc (MinIO Client):
mc share download minio-server/bucket-name/path/file.txt \
  --expires=24h

# Generate presigned URL (using AWS CLI style)
aws s3 presign s3://bucket-name/path/file.txt \
  --endpoint-url http://localhost:9000 \
  --expires-in 3600
```

## Bucket Permissions

### Modify Bucket Policies

```bash
# Using mc (MinIO Client) for detailed permission control:
mc policy set download minio-server/bucket-name
mc policy set upload minio-server/bucket-name
mc policy set public minio-server/bucket-name
mc policy set none minio-server/bucket-name

# View current policy
mc policy get minio-server/bucket-name
```

### Access Control

```bash
# Set anonymous read access
rclone config edit remote-name
# Add: acl = public-read

# View ACL
rclone info remote:bucket-name/path/
```

## Advanced Options

### Bandwidth Limiting

```bash
# Limit bandwidth to 10M
rclone copy source destination --bwlimit 10M

# Schedule bandwidth (off-peak)
rclone copy source destination --bwlimit "08:00,512k 18:00,10M"
```

### Filtering

```bash
# Include only certain files
rclone copy source destination --include "*.jpg" --include "*.png"

# Exclude files
rclone copy source destination --exclude "*.tmp" --exclude ".DS_Store"

# Use filter file
rclone copy source destination --filter-from filter-rules.txt
```

### Sync Options

```bash
# Dry run (preview changes)
rclone sync source destination --dry-run

# Delete files in destination not in source
rclone sync source destination

# Sync without deleting
rclone copy source destination

# Preserve timestamps
rclone sync source destination --times

# Check checksums instead of size
rclone sync source destination --checksum
```

## Common Patterns

### Upload and Share

```bash
# 1. Upload files
rclone copy local-folder minio-server:bucket-name/uploads/

# 2. Generate share link
mc share download minio-server/bucket-name/uploads/file.jpg --expires=24h
```

### Organize Media Files

```bash
# Organize by type
rclone copy ./images minio-server:media/images/
rclone copy ./videos minio-server:media/videos/
rclone copy ./books minio-server:media/books/
```

### Backup with Encryption

```bash
# Backup encrypted
rclone sync important-folder encrypted-minio:backup-$(date +%Y%m%d)/
```

## Troubleshooting

### Connection Issues

```bash
# Test connection
rclone ls remote:

# Verbose output for debugging
rclone ls remote: -vv
```

### Permission Issues

```bash
# Check access keys and permissions
rclone config show remote-name

# Verify MinIO policy
mc policy get minio-server/bucket-name
```

## Notes

- Always use `--dry-run` first with `sync` operations
- `rclone sync` is destructive - it makes destination match source
- Use `rclone copy` for non-destructive transfers
- MinIO-specific operations like policy management work best with `mc` client
- For production use, consider environment variables for secrets
