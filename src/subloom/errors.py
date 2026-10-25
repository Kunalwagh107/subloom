class SubloomError(Exception):
    """An actionable error safe to display to the user."""


class Cancelled(SubloomError):
    pass


class GPUError(SubloomError):
    pass
