from os.path import join
import subprocess
from logging import getLogger
from qamlib.utils import ensure_dir_exists, chdir
from mtui.messages import SvnCheckoutInterruptedError

logger = getLogger("mtui.template")


class _TemplateIOError(IOError):
    """
    New type to distinguish between IOErrors happening when reading the
    template file which are recoverable and IOErrors happening somewhere
    else in the process
    """

    pass


class TestReportAlreadyLoaded(RuntimeError):
    pass


def testreport_svn_checkout(config, path, id):
    """
    param: path type: str - svn base path - not handled by pathlib
    param: config type: instance of Config singleton
    param: id type: str - RequestReviewID 
    """
    ensure_dir_exists(
        config.template_dir,
        on_create=lambda path: logger.debug(
            "created config.template_dir directory {0}".format(path)
        ),
    )

    uri = join(path, id)
    with chdir(str(config.template_dir)):
        try:
            subprocess.check_call(["svn", "co", uri])
        except KeyboardInterrupt:
            raise SvnCheckoutInterruptedError(uri)
