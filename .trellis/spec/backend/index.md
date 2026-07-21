# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory contains guidelines for backend development. Fill in each file with your project's specific conventions.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | To fill |
| [Database Guidelines](./database-guidelines.md) | ORM patterns, queries, migrations | ✅ Filled — immutable model + append-only event patterns |
| [Error Handling](./error-handling.md) | Error types, handling strategies | To fill |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | ✅ Filled — superuser guard, secret loading, response signing, Range download |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | To fill |
| [Image Resource Bulk Delete](./image-resource-bulk-delete.md) | Tenant-safe partial-success bulk delete contract | Filled |
| [Image Resource Hash Deduplication](./image-resource-hash-deduplication.md) | Tenant-scoped SHA-256 upload and backfill contract | Filled |

---

## How to Fill These Guidelines

For each guideline file:

1. Document your project's **actual conventions** (not ideals)
2. Include **code examples** from your codebase
3. List **forbidden patterns** and why
4. Add **common mistakes** your team has made

The goal is to help AI assistants and new team members understand how YOUR project works.

---

**Language**: All documentation should be written in **English**.
