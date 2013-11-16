from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_redirect_model():
    """
    Returns the Redirect model that is active in this project.
    """
    from django.db.models import get_model

    try:
        app_label, model_name = settings.REDIRECT_MODEL.split('.')
    except ValueError:
        raise ImproperlyConfigured("REDIRECT_MODEL must be of the form 'app_label.model_name'")
    redirect_model = get_model(app_label, model_name)
    if redirect_model is None:
        raise ImproperlyConfigured("REDIRECT_MODEL refers to model '%s' that has not been installed" % settings.REDIRECT_MODEL)
    return redirect_model
