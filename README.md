# BotSkills 🤖

Picoclaw Bot Skills Repository - Centralized management for all Picoclaw bot skills.

## About

This repository contains all custom skills developed for the Picoclaw AI assistant. Each skill is a self-contained module that extends Picoclaw's capabilities.

## Available Skills

### rclone 📁
Comprehensive rclone control for MinIO and cloud storage operations.

**Features:**
- File operations: upload, download, sync, move, delete
- Bucket management: list, create, delete buckets
- MinIO-specific controls: view buckets, modify permissions
- Security: encryption settings, time-limited share links
- Configuration: manage rclone remotes

**Location:** `rclone/`

## Usage

Skills are automatically loaded by Picoclaw from this repository. To add a new skill:

1. Create a new directory for your skill
2. Add a `SKILL.md` file with skill documentation
3. Include any necessary scripts or reference documents
4. Commit and push to this repository

## Issue Tracking

If you encounter any problems with a skill:
1. Check existing issues in the [Issues](https://github.com/siciyuan404/BotSkills/issues) tab
2. Create a new issue with detailed information about the problem
3. Issues are automatically reviewed daily at 4:00 AM

## Contributing

Contributions are welcome! Please feel free to submit pull requests for new skills or improvements to existing ones.

## License

MIT License - See LICENSE file for details

---

**Repository**: https://github.com/siciyuan404/BotSkills
