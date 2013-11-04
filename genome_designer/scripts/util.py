import os
import pickle
import shutil
import sys

def setup_django_env():
    """Setting up the django/python env is a PITA but must be done."""
    # First make sure settings are on the path.
    PWD = os.path.dirname(os.path.realpath(__file__ ))
    settings_path = os.path.split(PWD)[0]
    os.sys.path.append(settings_path)

    # Now setup the environment using the settings
    from django.core import management
    try:
        import settings # Assumed to be in the os path
    except ImportError:
        sys.stderr.write(
                "Error: Can't find the file 'settings.py' in the directory " +
                "containing %r. It appears you've customized things.\nYou'll" +
                "have to run django-admin.py, passing it your settings " +
                "module.\n(If the file settings.py does indeed exist, it's " +
                "causing an ImportError somehow.)\n" % __file__)
        sys.exit(1)

    management.setup_environ(settings)

    # All of our scripts should maintain group writer permissions since we have
    # multiple different users potentially writing to files, though all are
    # in the genome-designer group.
    # We set the process umask here to enforce this.
    # TODO: Is there a better place to set this?
    os.umask(002)


def fn_runner(fn, project, args_list, concurrent=False):
    """Helper method that handles calling a method depending on whether
    concurrent is True or not.

    Returns:
        If concurrent=True, immediately returns a celery.Result object without
        blocking. Otherwise blocks while executing the function, returning an
        implicit None.
    """
    from main.tasks import generic_task
    from main.models import Project

    assert isinstance(project, Project)

    if concurrent:
        return generic_task.delay(fn.__name__, project, args_list)
    else:
        return generic_task.__call__(fn.__name__, project, args_list)
