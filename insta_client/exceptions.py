class InstaUserNotFoundError(Exception):
    pass


class InstaLoginRequiredError(Exception):
    pass


class InstaApiClientError(Exception):
    pass


class InstaWebClientError(Exception):
    pass


class BadRequestException(Exception):
    pass


class InvalidAccessTokenException(Exception):
    pass


class NotFoundException(Exception):
    pass


class RateLimitException(Exception):
    pass


class InstaWebRateLimitException(Exception):
    pass


class APINotAllowedError(Exception):
    pass