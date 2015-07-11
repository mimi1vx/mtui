# -*- coding: utf-8 -*-
# vim: et sw=2 sts=2

from os.path import basename
from os.path import splitext

from traceback import format_exc

import subprocess

from mtui import messages

class Script(object):
  """
  :type subdir: str
  :param subdir: subdirectory in the L{TestReport.scripts_wd} where the
    scripts are located.

    Note: also used as a "type of the script" and can be shown to
    the user.

  FIXME: should be an abstract attribute
  """

  def __init__(self, tr, path, log):
    """
    :type path: str
    :param path: absolute path to the script
    """
    self.path = path
    self.name = basename(path)
    self.testreport = tr
    self.log = log

  def __repr__(self):
    return "<{0}.{1} {2} for {3}>".format(
      self.__module__,
      self.__class__.__name__,
      self.path,
      repr(self.testreport),
    )

  def __str__(self):
    return "{0} script {1}".format(
      self.subdir,
      self.name,
    )

  def run(self, targets):
    """
    :type targets: [{HostsGroup}]
    """
    try:
      self.log.info('running {0}'.format(self))
      self._run(targets)
    except KeyboardInterrupt:
      self.log.warning('skipping {0}'.format(self))
      return

  def _filename(self, target = None, subdir = None):
    """
    :returns: str "fully qualified" file name
    """
    if not subdir:
      subdir = self.subdir

    xs = [subdir, splitext(self.name)[0]]
    if target:
      xs.append(target.hostname)

    return ".".join(xs)

class PreScript(Script):
  subdir = "pre"

  def _run(self, targets):
    targets.put(
      self.path,
      self.testreport.target_wd(self._filename()),
    )

    targets.put(
      self.testreport.pkg_list_file(),
      self.testreport.target_wd('package-list.txt'),
    )

    targets.run(
      "{exe} -r {repository} -p {pkg_list_file} {id}".format(
        exe = self.testreport.target_wd(self._filename()),
        repository = self.testreport.repository,
        pkg_list_file = self.testreport.target_wd('package-list.txt'),
        id  = self.testreport.id,
      )
    )

    for t in targets.values():
      fname = self.testreport.report_wd(
        'output/scripts',
        self._filename(t),
        filepath = True,
      )
      try:
        with open(fname, 'w') as f:
          f.write(t.lastout())
          f.write(t.lasterr())
      except IOError as e:
        self.log.error(messages.FailedToWriteScriptResult(fname, e))

class PostScript(PreScript):
  subdir = "post"

class CompareScript(Script):
  subdir = "compare"

  def _run(self, targets):
    for t in targets.values():
      self._run_single_target(t)

  def _result(self, s, t):
    return self.testreport.report_wd(
      'output/scripts',
      self._filename(
        subdir = s,
        target = t,
      ).replace("compare_", "check_"),
      filepath = True,
    )

  def _run_single_target(self, t):
    argv = [
      self.path,
      self._result(PreScript.subdir, t),
      self._result(PostScript.subdir, t),
    ]

    self.log.debug("running {0}".format(argv))
    stdout = stderr = None
    try:
      p = subprocess.Popen(
        argv,
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
      )
    except EnvironmentError as e:
      t.log.append([' '.join(argv), '', '', 0x100, 0])
      self.log.critical(messages.StartingCompareScriptError(e, argv))
      self.log.debug(format_exc())
      return

    (stdout, stderr) = p.communicate()
    rc = p.wait()

    t.log.append([' '.join(argv), str(stdout), str(stderr), rc, 0])

    if rc == 0:
      return

    if rc == 2:
      logger, msg = self.log.critical, messages.CompareScriptCrashed
    else:
      logger, msg = self.log.warning, messages.CompareScriptFailed

    assert callable(logger), "{0!r} not callable".format(logger)

    logger(msg(argv, stdout, stderr, rc))

