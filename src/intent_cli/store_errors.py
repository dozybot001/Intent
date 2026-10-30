"""What can go wrong with stored objects."""

from pathlib import Path


class StorageSecurityError(RuntimeError):
    """Base class for storage paths or data that are unsafe to use."""


class InvalidObjectIdError(StorageSecurityError):
    """Raised when an object ID cannot name an object of the requested type."""

    def __init__(self, object_type, obj_id):
        self.object_type = object_type
        self.obj_id = obj_id
        super().__init__(
            f"Invalid {object_type} ID {obj_id!r}; expected "
            f"'{object_type}-' followed by ASCII digits."
        )


class UnsafeStoragePathError(StorageSecurityError):
    """Raised when a storage path escapes or redirects the .intent boundary."""

    def __init__(self, path, message):
        self.path = Path(path)
        super().__init__(f"{message}: {self.path}")


class StoredObjectIntegrityError(StorageSecurityError):
    """Raised when a stored object's filename and identity fields disagree."""

    def __init__(self, path, message):
        self.path = Path(path)
        super().__init__(f"Invalid stored object at {self.path}: {message}")


class StoredObjectParseError(StorageSecurityError):
    """Raised when a stored object is not valid UTF-8 JSON."""

    def __init__(self, path, message):
        self.path = Path(path)
        super().__init__(f"Could not parse stored object at {self.path}: {message}")


class StoredObjectSchemaError(StorageSecurityError):
    """Raised when a stored object does not satisfy its required schema."""

    def __init__(self, path, message, *, field=None):
        self.path = Path(path)
        self.field = field
        super().__init__(f"Invalid stored object schema at {self.path}: {message}")


class StoredObjectWriteConflictError(StorageSecurityError):
    """Raised when an object create or update cannot preserve write semantics."""

    def __init__(self, path, message, *, conflicts=None):
        self.path = Path(path)
        self.conflicts = [str(conflict) for conflict in (conflicts or [])]
        super().__init__(f"Object write conflict at {self.path}: {message}")


class WorkspaceBusyError(RuntimeError):
    """Raised when another Intent writer holds the workspace lock."""

    def __init__(self, message, *, owner=None):
        self.owner = owner or {}
        super().__init__(message)
