# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import logging

__version__ = '0.0.10'
__all__ = ['logger', 'add_stderr_logger',
           'InstaSession', 'InstaApiClient', 'InstaWebClient',
           'InstaHashtag', 'InstaMedia', 'InstaUser']

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def add_stderr_logger(level=logging.DEBUG):
    """
    Helper for quickly adding a StreamHandler to the logger. Useful for
    debugging.

    Returns the handler after adding it.
    """
    _logger = logging.getLogger(__name__)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    _logger.addHandler(handler)
    _logger.setLevel(level)
    _logger.debug('Added a stderr logging handler to logger: %s', __name__)
    return handler


from .client import InstaApiClient, InstaWebClient
from .instagram import InstaHashtag, InstaMedia, InstaUser
from .session import InstaSession
