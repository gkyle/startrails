"""Shared cancellation across denoise stages using the common Observable base."""

from startrails.lib.util import Observable


class DenoiseOperation(Observable):
    """Denoise operation base retaining the existing import path."""

    pass
