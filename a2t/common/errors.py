class PseudoCodeRuntimeError(Exception):
    """Base exception for runtime errors inside pseudo-code semantics."""
    pass


class UserProgramCrashed(PseudoCodeRuntimeError):
    pass
