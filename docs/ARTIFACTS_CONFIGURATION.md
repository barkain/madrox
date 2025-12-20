# Artifacts Feature - Configuration Guide

## Overview

This guide covers all configuration options for the Artifacts feature, including environment variables, config file settings, and customization options.

## Configuration Sources

Configuration is loaded from three sources (in order of precedence):

1. **Environment Variables** (highest priority)
2. **Config File** (`config.py` or `orchestrator/config.py`)
3. **Default Values** (lowest priority)

## Environment Variables

## New Artifacts Configuration (DevOps Implementation)

### `ARTIFACTS_DIR`

**Type**: String (file path)

**Default**: `/tmp/madrox_logs/artifacts`

**Description**: Root directory where all team artifacts are stored with subdirectories for organization

**Example**:
```bash
export ARTIFACTS_DIR=/var/madrox/artifacts
python run_orchestrator.py
```

**Common Patterns**:
```bash
# Project-relative path
ARTIFACTS_DIR=./artifacts

# Absolute path
ARTIFACTS_DIR=/home/user/madrox/artifacts

# Temporary directory (for testing)
ARTIFACTS_DIR=/tmp/madrox-artifacts

# Network storage
ARTIFACTS_DIR=/mnt/shared/madrox/artifacts

# Cloud storage (with mounting)
ARTIFACTS_DIR=/mnt/s3/madrox/artifacts
```

**Directory Structure**:
```
/tmp/madrox_logs/artifacts/
├── by_instance/     # Organized by instance ID
├── by_team/         # Organized by team ID
└── by_date/         # Organized by collection date
```

**Requirements**:
- Parent directory must exist and be writable
- Must have at least 10GB available (recommended)
- Should have fast I/O characteristics

### `PRESERVE_ARTIFACTS`

**Type**: Boolean

**Default**: `true`

**Description**: Enable/disable automatic preservation of team artifacts to prevent data loss

**Example**:
```bash
# Enable artifact preservation (default)
export PRESERVE_ARTIFACTS=true
python run_orchestrator.py

# Disable preservation
export PRESERVE_ARTIFACTS=false
python run_orchestrator.py
```

**Behavior When Enabled**:
- Automatically collects team artifacts when work completes
- Preserves all matching files to artifacts directory
- Organizes by instance, team, and date
- Prevents loss of generated outputs

**Values**:
- `true` or `1` or `yes` - Preservation enabled
- `false` or `0` or `no` - Preservation disabled

### `ARTIFACT_PATTERNS`

**Type**: Comma-separated string

**Default**: `*.md,*.pdf,*.csv,*.json,FINAL_*`

**Description**: File patterns to automatically preserve when team completes

**Example**:
```bash
# Preserve specific file types
export ARTIFACT_PATTERNS="*.md,*.pdf,*.csv,*.json,FINAL_*"
python run_orchestrator.py

# Preserve additional outputs
export ARTIFACT_PATTERNS="*.md,*.pdf,*.json,report_*,FINAL_*,*.txt"
python run_orchestrator.py

# Preserve all files
export ARTIFACT_PATTERNS="*"
python run_orchestrator.py
```

**Pattern Syntax**:
- `*` - Match any characters (e.g., `*.md` matches all markdown files)
- `FINAL_*` - Match files starting with prefix (e.g., `FINAL_report.pdf`)
- `?` - Match single character
- `[abc]` - Match a, b, or c
- Patterns are case-sensitive

**Common Patterns**:
```bash
# Documentation
ARTIFACT_PATTERNS="*.md,*.pdf,*.txt,*.rst"

# Data files
ARTIFACT_PATTERNS="*.csv,*.json,*.xml,*.xlsx"

# Reports
ARTIFACT_PATTERNS="report_*,FINAL_*,summary_*"

# Mixed
ARTIFACT_PATTERNS="*.md,*.pdf,*.csv,*.json,FINAL_*,report_*"
```

**Behavior**:
- Patterns are matched against filenames in team workspace
- Matching files are collected when `PRESERVE_ARTIFACTS=true`
- Multiple patterns separated by commas
- All whitespace is trimmed from patterns
- Patterns are evaluated in order (first match wins)

### `ARTIFACTS_ENABLED`

**Type**: Boolean

**Default**: `true`

**Description**: Enable/disable artifacts feature globally

**Example**:
```bash
# Disable artifacts collection
export ARTIFACTS_ENABLED=false
python run_orchestrator.py

# Enable explicitly
export ARTIFACTS_ENABLED=true
python run_orchestrator.py
```

**Values**:
- `true` or `1` or `yes` - Artifacts enabled
- `false` or `0` or `no` - Artifacts disabled

### `ARTIFACTS_COMPRESS`

**Type**: Boolean

**Default**: `false`

**Description**: Automatically gzip artifact directories after collection

**Example**:
```bash
export ARTIFACTS_COMPRESS=true
python run_orchestrator.py
```

**Behavior When Enabled**:
- Artifacts directory is gzipped to `.tar.gz` after collection
- Original directory is removed
- Size typically reduced to 20-40% of original
- Unpacking required for access

**Performance Impact**:
- Adds 5-10% to collection time
- Reduces disk storage by 60-80%
- Reduces I/O bandwidth requirements

### `ARTIFACTS_RETENTION_DAYS`

**Type**: Integer (number of days)

**Default**: `null` (no automatic cleanup)

**Description**: Automatically delete artifacts older than N days

**Example**:
```bash
# Keep artifacts for 30 days, then auto-delete
export ARTIFACTS_RETENTION_DAYS=30
python run_orchestrator.py

# Keep artifacts for 1 year
export ARTIFACTS_RETENTION_DAYS=365
python run_orchestrator.py
```

**Behavior**:
- Runs daily cleanup check at 2 AM
- Deletes directories older than specified days
- Only deletes complete sessions (all instances processed)
- Logs deletion activity

**Recommendations**:
- Development: `7` days
- Staging: `30` days
- Production: `90-365` days

### `ARTIFACTS_MAX_SIZE_GB`

**Type**: Integer (gigabytes)

**Default**: `null` (no size limit)

**Description**: Maximum total artifacts directory size before enforcement

**Example**:
```bash
# Enforce 100GB maximum
export ARTIFACTS_MAX_SIZE_GB=100
python run_orchestrator.py
```

**Behavior When Exceeded**:
- New artifact collections are rejected
- Returns error: "Artifacts storage limit exceeded"
- Oldest artifacts are flagged for cleanup
- System logs warning

**Enforcement**:
- Checked before artifact collection
- Checked every 24 hours
- Suggests oldest artifacts for manual deletion

### `ARTIFACTS_PATTERNS`

**Type**: Comma-separated string or JSON array

**Default**: `*.py,*.md,*.json,*.txt,*.csv,*.log`

**Description**: File patterns to include in workspace artifacts

**Example** (environment variable):
```bash
# Include specific file types
export ARTIFACTS_PATTERNS="*.py,*.md,*.txt,*.json"
python run_orchestrator.py

# Include all files (careful with large workspaces)
export ARTIFACTS_PATTERNS="*"
python run_orchestrator.py
```

**Example** (config file):
```python
config = {
    "artifacts_patterns": [
        "*.py",
        "*.md",
        "*.json",
        "*.txt",
        "requirements.txt",
        "Dockerfile",
        ".env.example",
        "docs/**/*"
    ]
}
```

**Pattern Syntax**:
- `*` - Match any characters in current level
- `**` - Match any characters in current and subdirectories
- `?` - Match single character
- `[abc]` - Match a, b, or c

**Common Patterns**:

```
# Code files
*.py, *.js, *.ts, *.go, *.rs, *.java

# Documentation
*.md, *.rst, *.txt, docs/**/*

# Data files
*.json, *.yaml, *.csv, *.xml

# Configuration
*.yml, *.env, *.toml, *.ini

# Build output
build/**, dist/**, target/**
```

**Exclusion Patterns** (use negation):
```python
artifacts_patterns = [
    "*",           # Include all files
    "!**/.git",    # Exclude .git
    "!**/node_modules",
    "!**/__pycache__",
    "!**.pyc"
]
```

### `ARTIFACTS_EXCLUDE_PATTERNS`

**Type**: Comma-separated string or JSON array

**Default**: `.git,__pycache__,.pytest_cache,.venv,node_modules,*.pyc`

**Description**: File patterns to exclude from artifacts

**Example**:
```bash
export ARTIFACTS_EXCLUDE_PATTERNS=".git,__pycache__,node_modules,.venv,*.tmp"
python run_orchestrator.py
```

**Example** (config file):
```python
config = {
    "artifacts_exclude_patterns": [
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "dist",
        "build",
        "*.pyc",
        "*.tmp",
        ".DS_Store"
    ]
}
```

### `ARTIFACTS_COPY_METADATA_ONLY`

**Type**: Boolean

**Default**: `false`

**Description**: Only collect metadata and output logs, skip workspace files

**Example**:
```bash
# Lightweight artifacts (metadata only)
export ARTIFACTS_COPY_METADATA_ONLY=true
python run_orchestrator.py
```

**Use Cases**:
- High-volume artifact collection (hundreds of teams)
- Limited disk space
- Separate workspace archival process
- Metadata analysis only

**What's Included**:
- Instance metadata (role, model, timestamps, tokens)
- Output transcripts (logs)
- Team summary (aggregated stats)
- Error messages and warnings

**What's Excluded**:
- Workspace files
- Generated outputs
- Data files
- Log files

## Configuration File

### Location

```
madrox/
├── config/
│   ├── orchestrator.toml
│   └── artifacts.yml
├── orchestrator/
│   └── config.py
└── run_orchestrator.py
```

### Format Options

**Python** (`orchestrator/config.py`):
```python
config = {
    "artifacts_dir": "./artifacts",
    "artifacts_enabled": True,
    "artifacts_compress": False,
    "artifacts_retention_days": 30,
    "artifacts_max_size_gb": 100,
    "artifacts_patterns": [
        "*.py",
        "*.md",
        "*.json",
        "requirements.txt"
    ],
    "artifacts_exclude_patterns": [
        ".git",
        "__pycache__",
        "node_modules"
    ]
}
```

**YAML** (`config/artifacts.yml`):
```yaml
artifacts:
  enabled: true
  directory: ./artifacts
  compress: false
  retention:
    days: 30
    auto_cleanup: true
    cleanup_time: "02:00"  # 2 AM
  storage:
    max_size_gb: 100
    check_interval_hours: 24
  patterns:
    include:
      - "*.py"
      - "*.md"
      - "*.json"
      - "requirements.txt"
    exclude:
      - ".git"
      - "__pycache__"
      - "node_modules"
      - ".venv"
      - "dist"
      - "build"
```

**TOML** (`config/orchestrator.toml`):
```toml
[artifacts]
enabled = true
directory = "./artifacts"
compress = false

[artifacts.retention]
days = 30
auto_cleanup = true
cleanup_time = "02:00"

[artifacts.storage]
max_size_gb = 100
check_interval_hours = 24

[artifacts.patterns]
include = [
    "*.py",
    "*.md",
    "*.json",
    "requirements.txt"
]
exclude = [
    ".git",
    "__pycache__",
    "node_modules"
]
```

## Configuration Loading

### Environment Variables Override Config File

```python
# config.py
config = {
    "artifacts_dir": "./artifacts",
    "artifacts_retention_days": 30,
}

# If environment variable is set:
# ARTIFACTS_DIR=/var/artifacts ARTIFACTS_RETENTION_DAYS=90 python run_orchestrator.py
# Result: artifacts_dir = "/var/artifacts", artifacts_retention_days = 90
```

### Default Configuration

```python
DEFAULT_CONFIG = {
    "artifacts_dir": "./artifacts",
    "artifacts_enabled": True,
    "artifacts_compress": False,
    "artifacts_retention_days": None,
    "artifacts_max_size_gb": None,
    "artifacts_patterns": [
        "*.py",
        "*.md",
        "*.json",
        "*.txt",
        "*.csv",
        "*.log",
        "*.yml",
        "*.yaml",
        "requirements.txt",
        "package.json",
        "Makefile",
        "README*"
    ],
    "artifacts_exclude_patterns": [
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "*.pyc",
        "*.egg-info",
        ".DS_Store",
        "Thumbs.db"
    ],
    "artifacts_copy_metadata_only": False
}
```

## Configuration Validation

### Startup Validation

On startup, the system validates:

1. **Directory Accessibility**
   ```python
   if not os.access(artifacts_dir, os.W_OK):
       raise ConfigError(f"Artifacts directory not writable: {artifacts_dir}")
   ```

2. **Retention Days Range**
   ```python
   if retention_days is not None and retention_days < 1:
       raise ConfigError("artifacts_retention_days must be >= 1")
   ```

3. **Storage Size Range**
   ```python
   if max_size_gb is not None and max_size_gb < 1:
       raise ConfigError("artifacts_max_size_gb must be >= 1")
   ```

4. **Pattern Syntax**
   ```python
   for pattern in artifacts_patterns:
       if not is_valid_glob_pattern(pattern):
           raise ConfigError(f"Invalid pattern: {pattern}")
   ```

### Configuration Error Messages

**Permission Error**:
```
ERROR: Artifacts directory not writable: /var/artifacts
       User: nobody
       Required permissions: write, execute
       Solution: Run as appropriate user or change ARTIFACTS_DIR
```

**Invalid Retention Days**:
```
ERROR: Invalid retention_days configuration: -5
       artifacts_retention_days must be positive integer or null
       Solution: Use value >= 1 or set to null
```

**Pattern Validation Error**:
```
ERROR: Invalid glob pattern: [invalid
       Unmatched bracket in pattern
       Solution: Check pattern syntax for glob compatibility
```

## Common Configuration Scenarios

### Scenario 1: Development Environment

```python
# Maximum artifact preservation, minimal constraints
config = {
    "artifacts_dir": "./artifacts",
    "artifacts_enabled": True,
    "artifacts_compress": False,
    "artifacts_retention_days": 7,      # Auto-cleanup old development artifacts
    "artifacts_max_size_gb": None,      # No size limit
    "artifacts_patterns": ["*"],        # Include everything
}
```

### Scenario 2: Production Environment

```python
# Balanced storage and retention
config = {
    "artifacts_dir": "/var/lib/madrox/artifacts",
    "artifacts_enabled": True,
    "artifacts_compress": True,         # Save space
    "artifacts_retention_days": 90,     # 3 months retention
    "artifacts_max_size_gb": 500,       # Enforce 500GB limit
    "artifacts_patterns": [
        "*.py", "*.md", "*.json",
        "requirements.txt", "Dockerfile",
        "logs/**/*"
    ],
    "artifacts_exclude_patterns": [
        ".git", "__pycache__", "node_modules",
        "*.pyc", ".DS_Store", "test-results"
    ]
}
```

### Scenario 3: Cloud Deployment (AWS S3)

```python
# Use S3-mounted filesystem
config = {
    "artifacts_dir": "/mnt/s3-artifacts",
    "artifacts_enabled": True,
    "artifacts_compress": True,
    "artifacts_retention_days": 365,    # 1 year retention
    "artifacts_max_size_gb": 5000,      # 5TB limit
    "artifacts_patterns": [
        "*.py", "*.md", "*.json",
        "reports/**/*", "models/**/*"
    ]
}

# Mount S3 bucket:
# aws s3 mount s3://my-bucket /mnt/s3-artifacts
```

### Scenario 4: High-Volume Teams

```python
# Lightweight artifacts for rapid cycling
config = {
    "artifacts_dir": "/data/artifacts",
    "artifacts_enabled": True,
    "artifacts_compress": True,
    "artifacts_retention_days": 14,
    "artifacts_max_size_gb": 100,
    "artifacts_copy_metadata_only": True,  # Skip workspace files
    "artifacts_patterns": [],  # Not used when metadata_only=True
}
```

### Scenario 5: Research/Experimentation

```python
# Preserve everything for analysis
config = {
    "artifacts_dir": "/research/artifacts",
    "artifacts_enabled": True,
    "artifacts_compress": False,        # Keep uncompressed for quick access
    "artifacts_retention_days": None,   # Never auto-delete
    "artifacts_max_size_gb": None,      # No limit
    "artifacts_patterns": ["*"],        # Everything
    "artifacts_exclude_patterns": [
        ".git",          # But skip version control
        "__pycache__",
        "node_modules"
    ]
}
```

## Configuration Examples

### .env File

```bash
# .env
ARTIFACTS_DIR=/var/madrox/artifacts
ARTIFACTS_ENABLED=true
ARTIFACTS_COMPRESS=true
ARTIFACTS_RETENTION_DAYS=30
ARTIFACTS_MAX_SIZE_GB=100
ARTIFACTS_PATTERNS="*.py,*.md,*.json,requirements.txt"
ARTIFACTS_EXCLUDE_PATTERNS=".git,__pycache__,node_modules"
```

## Runtime Configuration Changes

### Checking Current Configuration

```bash
# View current configuration
curl http://localhost:8001/config

# Response:
{
  "artifacts_dir": "./artifacts",
  "artifacts_enabled": true,
  "artifacts_compress": false,
  "artifacts_retention_days": 30,
  "artifacts_max_size_gb": 100
}
```

### Dynamic Configuration (Future)

Planned feature for runtime configuration updates:

```python
# Set configuration at runtime
manager.set_config({
    "artifacts_retention_days": 60,
    "artifacts_compress": True
})

# Configuration takes effect immediately
# Existing artifact collection jobs unaffected
```

## Troubleshooting Configuration Issues

### Issue: Artifacts Directory Creation Fails

**Symptoms**:
```
ERROR: Failed to create artifacts directory: Permission denied
```

**Solutions**:
```bash
# Check permissions on parent directory
ls -la $(dirname /var/artifacts)

# Create directory with proper permissions
sudo mkdir -p /var/artifacts
sudo chown madrox:madrox /var/artifacts
sudo chmod 755 /var/artifacts

# Or use user-accessible location
export ARTIFACTS_DIR=$HOME/artifacts
```

### Issue: Storage Limit Exceeded

**Symptoms**:
```
ERROR: Artifacts storage limit exceeded: 105GB > 100GB max
```

**Solutions**:
```bash
# Increase limit
export ARTIFACTS_MAX_SIZE_GB=150

# Or enable compression
export ARTIFACTS_COMPRESS=true

# Or reduce retention
export ARTIFACTS_RETENTION_DAYS=15

# Or cleanup oldest artifacts
find ./artifacts -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;
```

### Issue: Patterns Not Matching Files

**Symptoms**:
```
Workspace has 50 files but only 5 in artifacts
```

**Solutions**:
```bash
# Check pattern syntax
python -c "from fnmatch import fnmatch; print(fnmatch.fnmatch('test.py', '*.py'))"

# Use wildcard for all
export ARTIFACTS_PATTERNS="*"

# Check exclusion patterns aren't too broad
echo "Exclude patterns: $ARTIFACTS_EXCLUDE_PATTERNS"
```

## Best Practices

### 1. Set Appropriate Retention Policy

```bash
# Development: 1 week
ARTIFACTS_RETENTION_DAYS=7

# Staging: 1 month
ARTIFACTS_RETENTION_DAYS=30

# Production: 3 months
ARTIFACTS_RETENTION_DAYS=90
```

### 2. Monitor Disk Usage

```bash
# Set up monitoring
df -h /var/artifacts

# Get artifacts size
du -sh ./artifacts

# Track growth
watch -n 3600 'du -sh ./artifacts'
```

### 3. Use Compression in Production

```bash
# Enable compression to reduce storage
ARTIFACTS_COMPRESS=true
ARTIFACTS_MAX_SIZE_GB=100
```

### 4. Regularly Verify Access

```bash
# Test write access
touch /var/artifacts/test && rm /var/artifacts/test

# Test disk space
df -h /var/artifacts
```

### 5. Document Custom Patterns

```python
# In config file, explain pattern rationale
artifacts_patterns = [
    "*.py",      # Source code
    "*.md",      # Documentation
    "*.json",    # Configuration and data
    "reports/**/*",  # Generated reports
    # Exclude:
    # - compiled: *.pyc, __pycache__
    # - dependencies: node_modules, .venv
    # - version control: .git
]
```

## See Also

- [ARTIFACTS_FEATURE.md](ARTIFACTS_FEATURE.md) - Feature overview
- [ARTIFACTS_MCP_TOOLS.md](ARTIFACTS_MCP_TOOLS.md) - API tool reference
- [ARTIFACTS_METADATA.md](ARTIFACTS_METADATA.md) - Metadata format
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - General troubleshooting
