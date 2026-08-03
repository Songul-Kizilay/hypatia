# Database Architecture

> "Different types of knowledge require different types of storage."

---

# Purpose

This document describes the storage architecture of Hypatia.

Rather than relying on a single database, Hypatia uses multiple specialized storage systems optimized for different types of information.

The Brain interacts with storage only through the Memory Manager and Knowledge Interface.

---

# Design Principles

The database architecture follows these principles:

- Local-First
- Modular
- Secure
- Encrypted
- Explainable
- Scalable
- Versioned
- Backup-Friendly
- AI-Optimized

---

# High-Level Architecture

```
                    Brain Core
                         │
                         ▼
               Memory Manager
                         │
                         ▼
              Knowledge Interface
                         │
 ┌────────────┬────────────┬────────────┬────────────┐
 │            │            │            │
Relational  Vector DB  Knowledge Graph  File Storage
 Database
```

---

# Storage Types

Hypatia uses multiple storage systems.

---

## Relational Database

Used for structured information.

Examples:

- User Profiles
- Projects
- Tasks
- Settings
- Devices
- Permissions
- Jobs
- Workflows

Possible implementations:

- SQLite
- PostgreSQL

---

## Vector Database

Used for semantic search.

Stores:

- Embeddings
- Memory Embeddings
- Knowledge Embeddings
- Document Embeddings
- Conversation Embeddings

Supports:

- RAG
- Similarity Search
- Context Retrieval

Possible implementations:

- ChromaDB
- FAISS
- Qdrant

---

## Knowledge Graph

Represents relationships.

Examples:

```
User

↓

Cybersecurity

↓

PortSwigger

↓

SQL Injection

↓

Labs
```

Supports:

- Relationship discovery
- Connected reasoning
- Knowledge expansion

Possible implementations:

- Neo4j
- Memgraph

---

## File Storage

Stores raw files.

Examples:

- PDFs
- Images
- Videos
- Audio
- Documents
- Backups
- Research Notes

Location:

```
storage/
```

---

# Memory Storage

Managed exclusively by the Memory Manager.

Stores:

- Working Memory
- Short-Term Memory
- Long-Term Memory
- Semantic Memory
- Episodic Memory
- Procedural Memory

---

# Knowledge Storage

Managed by the Knowledge Interface.

Stores:

- Books
- Articles
- Papers
- Documentation
- Notes
- CVEs
- Writeups
- Videos

---

# Index Storage

Indexes accelerate retrieval.

Examples:

- Memory Index
- Document Index
- Embedding Index
- Search Index

---

# Cache

Frequently accessed data remains cached.

Benefits:

- Faster responses
- Lower latency
- Reduced disk access

---

# Backup Strategy

Automatic backups support:

- Local Backup
- External Drive
- NAS
- Optional Encrypted Cloud Backup

Users control backup policies.

---

# Synchronization

Future versions may synchronize:

- Desktop
- Laptop
- Phone
- Watch
- Robot

Synchronization follows a Local-First strategy.

---

# Security

All sensitive information should be encrypted.

Requirements:

- Encryption at Rest
- Encryption in Transit
- Permission Validation
- Audit Logging
- Access Control

---

# Database Relationships

```
Relational Database

↓

Knowledge Graph

↓

Vector Database

↓

File Storage
```

Each storage type has a specialized responsibility.

---

# Scalability

The storage architecture supports:

- Multiple Databases
- Multiple Vector Stores
- Distributed Storage
- NAS
- Cloud Replication
- Edge Devices

---

# Future Vision

Future versions may support:

- Federated Storage
- Distributed Knowledge Graphs
- Automatic Data Tiering
- Intelligent Storage Optimization
- Self-Healing Databases
- AI-Based Index Optimization

---

# Final Statement

Hypatia's database architecture combines relational databases, vector databases, knowledge graphs, and file storage into a unified Local-First storage ecosystem.

Each storage system performs a specialized role while remaining coordinated through the Memory Manager and Knowledge Interface.