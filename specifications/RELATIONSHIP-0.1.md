# Relationship v0.1

R3 treats relationships as first-class canonical records. Relationships are not stored only as
nested object fields.

The executable JSON Schema is [`aeir/RELATIONSHIP-0.1.schema.json`](aeir/RELATIONSHIP-0.1.schema.json).

Each relationship records:

- stable relationship id;
- supported relationship type;
- source and target AEIR object ids;
- lifecycle, truth, and approval status;
- source references;
- confidence;
- version;
- validity dates;
- immutable audit metadata.

Relationship endpoints must exist in the same AEIR project model. Duplicate relationship ids and
self-referential relationships are rejected by the canonical model.
