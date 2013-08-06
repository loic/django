"""
Global Django exception and warning classes.
"""
from functools import reduce
import operator

from django.utils.encoding import force_text


class DjangoRuntimeWarning(RuntimeWarning):
    pass


class ObjectDoesNotExist(Exception):
    """The requested object does not exist"""
    silent_variable_failure = True


class MultipleObjectsReturned(Exception):
    """The query returned multiple objects when only one was expected."""
    pass


class SuspiciousOperation(Exception):
    """The user did something suspicious"""


class SuspiciousMultipartForm(SuspiciousOperation):
    """Suspect MIME request in multipart form data"""
    pass


class SuspiciousFileOperation(SuspiciousOperation):
    """A Suspicious filesystem operation was attempted"""
    pass


class DisallowedHost(SuspiciousOperation):
    """HTTP_HOST header contains invalid value"""
    pass


class DisallowedRedirect(SuspiciousOperation):
    """Redirect to scheme not in allowed list"""
    pass


class PermissionDenied(Exception):
    """The user did not have permission to do that"""
    pass


class ViewDoesNotExist(Exception):
    """The requested view does not exist"""
    pass


class MiddlewareNotUsed(Exception):
    """This middleware is not used in this server configuration"""
    pass


class ImproperlyConfigured(Exception):
    """Django is somehow improperly configured"""
    pass


class FieldError(Exception):
    """Some kind of problem with a model field."""
    pass


NON_FIELD_ERRORS = '__all__'


class ValidationError(Exception):
    """An error while validating data."""
    def __init__(self, message, code=None, params=None):
        """
        The `message` parameter can be a single error message, a list of error
        messages or a dict that maps field names to lists of error messages.
        What we define as an "error message" can be either a simple string
        or an instance of ValidationError with its message attribute set.
        """
        if isinstance(message, ValidationError):
            self.__dict__.update(message.__dict__)

        elif isinstance(message, dict):
            self.error_dict = {}
            for field, messages in message.items():
                if not isinstance(messages, ValidationError):
                    messages = ValidationError(messages)
                self.error_dict[field] = messages.error_list

        elif isinstance(message, list):
            self.error_list = []
            for message in list(message):
                # Normalize plain strings to instances of ValidationError.
                if not isinstance(message, ValidationError):
                    message = ValidationError(message)
                self.error_list.extend(message.error_list)

        else:
            self.message = message
            self.code = code
            self.params = params
            self.error_list = [self]

    @property
    def message_dict(self):
        return dict(self)

    @property
    def messages(self):
        if hasattr(self, 'error_dict'):
            return reduce(operator.add, dict(self).values())
        return list(self)

    def update_error_dict(self, error_dict):
        if hasattr(self, 'error_dict'):
            if error_dict:
                for field, errors in self.error_dict.items():
                    error_dict.setdefault(field, []).extend(errors)
            else:
                error_dict = self.error_dict
        else:
            error_dict[NON_FIELD_ERRORS] = self.error_list
        return error_dict

    def __iter__(self):
        if hasattr(self, 'error_dict'):
            for field, errors in self.error_dict.items():
                yield field, list(ValidationError(errors))
        else:
            for error in self.error_list:
                message = error.message
                if error.params:
                    message %= error.params
                yield force_text(message)

    def __str__(self):
        if hasattr(self, 'error_dict'):
            return repr(dict(self))
        return repr(list(self))

    def __repr__(self):
        return 'ValidationError(%s)' % self
