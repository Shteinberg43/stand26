class PseudoCodeRuntimeError(Exception):
    """Base class for user-program runtime failures inside the pseudocode interpreter."""


class UserProgramCrashed(PseudoCodeRuntimeError):
    """Raised when a user algorithm crashes during execution."""