from contextvars import ContextVar

request_id = ContextVar("request_id", default=None)


def set_request_id(value):
    request_id.set(value)


def get_request_id():
    return request_id.get()