class AuditError(Exception):
    code = "audit_error"


class AuditProjectNotFoundError(AuditError):
    code = "audit_project_not_found"


class InvalidAuditCursorError(AuditError):
    code = "invalid_audit_cursor"


class AuditExportError(AuditError):
    code = "audit_export_error"


class AuditIntegrityError(AuditError):
    code = "audit_integrity_error"
