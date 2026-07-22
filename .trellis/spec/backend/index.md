# Backend Development Guidelines

> Best practices for backend development in this project.

---

## Overview

This directory contains guidelines for backend development. Fill in each file with your project's specific conventions.

---

## Guidelines Index

| [Directory Structure](./directory-structure.md) | Module organization and file layout | ✅ Filled |
| [Error Handling](./error-handling.md) | Error types, handling strategies | ✅ Filled |
| [Database Guidelines](./database-guidelines.md) | ORM patterns, queries, migrations | ✅ Filled |
| [Logging Guidelines](./logging-guidelines.md) | Structured logging, log levels | ✅ Filled |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | ✅ Filled |
| [API Design](./api-design.md) | REST URL conventions, ViewSet patterns, pagination | ✅ Filled |
| [Security Guidelines](./security-guidelines.md) | Auth, authorization, tenant isolation, secrets | ✅ Filled |
| [Testing Strategy](./testing-strategy.md) | Test framework, mock patterns, WS testing | ✅ Filled |
| [Image Resource Bulk Delete](./image-resource-bulk-delete.md) | Tenant-safe partial-success bulk delete | Filled |
| [Image Resource Hash Deduplication](./image-resource-hash-deduplication.md) | Tenant-scoped SHA-256 dedup | Filled |
| [Aliyun Bailian Managed RAG](./aliyun-bailian-managed-rag.md) | Managed RAG: indexing, retrieval, credentials | Filled |

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
