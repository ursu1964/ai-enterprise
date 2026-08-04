# AEIR knowledge storage v0.1

PostgreSQL is the system of record for versioned AEIR models. Each immutable model version retains
its canonical document and hash while its objects and relationships are also projected into
relational tables for direct querying. Extensible source and object attributes use JSONB.

Uploaded source bytes remain in S3-compatible object storage. PostgreSQL stores their provider,
bucket, immutable object key, content hash, media type, size, original filename, uploader, and
extensible metadata; it does not duplicate uploaded file content.

The storage port is provider-neutral. The first laptop adapter is local and content-addressed; a
production S3-compatible adapter can implement the same immutable locator and hash-verification
contract without changing canonical persistence.

Every model-version append produces a hash-linked change event in the same transaction. PostgreSQL
enforces model versions, object projections, relationships, source metadata, and change events as
append-only with triggers that reject updates and deletes.
Project-row locking serializes version allocation, and database uniqueness constraints provide a
second race-safety boundary. No graph database is introduced.
