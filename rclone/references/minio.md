# MinIO Specific Operations

## MinIO Client (mc) Commands

While rclone handles file operations, the MinIO Client (mc) provides additional management features.

### Installation

```bash
# Windows (using chocolatey)
choco install minio-client

# Or download binary from https://min.io/download
```

### Configuration

```bash
# Add MinIO server
mc alias set minio-server http://localhost:9000 ACCESS_KEY SECRET_KEY

# List configured aliases
mc alias list
```

### Bucket Policy Management

```bash
# Set policy to download only
mc policy set download minio-server/bucket-name

# Set policy to upload only
mc policy set upload minio-server/bucket-name

# Set policy to public (read/write)
mc policy set public minio-server/bucket-name

# Set policy to none (private)
mc policy set none minio-server/bucket-name

# Get current policy
mc policy get minio-server/bucket-name

# List all policies
mc policy list minio-server
```

### Share Links

```bash
# Generate download link with expiration
mc share download minio-server/bucket-name/path/file.jpg --expires=24h

# Generate upload link with expiration
mc share upload minio-server/bucket-name/path/ --expires=1h

# Share entire bucket
mc share download minio-server/bucket-name --expires=7d
```

### User Management

```bash
# List users
mc admin user list minio-server

# Create user
mc admin user add minio-server username password

# Disable user
mc admin user disable minio-server username

# Enable user
mc admin user enable minio-server username

# Remove user
mc admin user remove minio-server username
```

### Group Management

```bash
# List groups
mc admin group list minio-server

# Create group
mc admin group add minio-server groupname username1 username2

# Remove user from group
mc admin group remove minio-server groupname username

# Delete group
mc admin group remove minio-server groupname
```

### Policy Files

Create custom policy files (JSON):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::bucket-name/*"
      ]
    }
  ]
}
```

Apply custom policy:

```bash
mc admin policy create minio-server custom-policy policy.json
mc admin policy attach minio-server custom-policy --user username
```

## Rclone MinIO Configuration

### Basic MinIO Remote

```bash
rclone config create minio-server s3 \
  --s3-provider Minio \
  --s3-endpoint http://localhost:9000 \
  --s3-access-key YOUR_ACCESS_KEY \
  --s3-secret-key YOUR_SECRET_KEY \
  --s3-region us-east-1
```

### With SSL/TLS

```bash
rclone config create minio-server s3 \
  --s3-provider Minio \
  --s3-endpoint https://minio.example.com \
  --s3-access-key YOUR_ACCESS_KEY \
  --s3-secret-key YOUR_SECRET_KEY \
  --s3-region us-east-1
```

### With Custom CA Certificate

```bash
rclone config create minio-server s3 \
  --s3-provider Minio \
  --s3-endpoint https://minio.example.com \
  --s3-access-key YOUR_ACCESS_KEY \
  --s3-secret-key YOUR_SECRET_KEY \
  --s3-region us-east-1 \
  --s3-ca-cert /path/to/ca.crt
```

## Encryption Options

### Server-Side Encryption (SSE)

Configure MinIO bucket with SSE:

```bash
mc encrypt set sse-s3 minio-server/bucket-name
```

### Client-Side Encryption with Rclone

Create crypt remote:

```bash
rclone config create encrypted-minio crypt \
  --crypt-remote minio-server:bucket-name \
  --crypt-password YOUR_PASSWORD \
  --crypt-password2 YOUR_SALT
```

Use the encrypted remote:

```bash
# Upload encrypted
rclone copy local-file encrypted-minio:path/

# Download (auto-decrypt)
rclone copy encrypted-minio:path/ local-folder
```

## Versioning

Enable versioning on a bucket:

```bash
mc version enable minio-server/bucket-name
```

List versions:

```bash
mc ls --versions minio-server/bucket-name/path/
```

Restore previous version:

```bash
mc cp --attr "version-id=VERSION_ID" minio-server/bucket-name/path/file.txt \
  minio-server/bucket-name/path/file.txt
```

## Lifecycle Management

Set up lifecycle rules:

```json
{
  "Rules": [
    {
      "ID": "ExpireOldFiles",
      "Status": "Enabled",
      "Filter": {
        "Prefix": ""
      },
      "Expiration": {
        "Days": 90
      }
    }
  ]
}
```

Apply lifecycle rule:

```bash
mc ilm import minio-server/bucket-name < lifecycle.json
```

## Monitoring

### Server Info

```bash
mc admin info minio-server
```

### Service Status

```bash
mc admin service status minio-server
```

### Top (slow operations)

```bash
mc admin top locks minio-server
mc admin top drive minio-server
```

## Troubleshooting

### Connection Issues

```bash
# Test with mc
mc ls minio-server

# Test with rclone
rclone ls minio-server:

# Verbose mode
rclone ls minio-server: -vv
```

### Permission Issues

```bash
# Check user policy
mc admin policy info minio-server policy-name

# Check user membership
mc admin user info minio-server username
```

### Common Error Codes

- `AccessDenied`: Check user permissions and bucket policy
- `NoSuchBucket`: Verify bucket name and spelling
- `InvalidAccessKeyId`: Check access key configuration
- `SignatureDoesNotMatch`: Check secret key configuration
