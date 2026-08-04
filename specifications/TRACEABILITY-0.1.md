# AEIR traceability v0.1

The Step 8 traceability contract records formal source mappings for every generated section and
entry in the first artifact bundle.

The traceability manifest is deterministic and tamper-evident. It binds:

- the exact AEIR model hash;
- the exact source AEPM manifest hash;
- the exact artifact bundle hash;
- a catalog of non-rejected AEIR source objects;
- a catalog of AEIR relationships used by generated sections or entries;
- one section trace for every generated artifact section;
- one entry trace for every generated artifact entry;
- a canonical manifest SHA-256 hash.

Every section and entry trace contains the artifact type, artifact hash, section key, content hash,
source AEIR object identifiers, and relationship identifiers when relationships are part of the
projection. Source objects retain their canonical status, source kind, original source reference,
source manifest hash, evidence references, and object hash.

Empty sections are traced to the project object and the exact AEIR model hash. This records that the
absence statement is derived from the canonical model rather than invented prose.

Traceable Markdown rendering is a pure projection that appends source object identifiers and client
source references to each generated section. The plain artifact compiler output remains unchanged;
the traceability contract is the authority for provenance.

Validation fails closed when:

- the manifest hash is wrong;
- a section or entry mapping references an unknown source object;
- a mapping references an unknown relationship;
- source objects, relationships, section traces, or entry traces are duplicated;
- mappings are not sorted deterministically;
- the manifest does not match the supplied AEIR model and artifact bundle.
