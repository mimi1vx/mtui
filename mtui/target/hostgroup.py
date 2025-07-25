import re
from collections import UserDict
from logging import getLogger
from pathlib import Path
from typing import Self, final

from ..exceptions import UpdateError
from ..hooks import CompareScript, PostScript, PreScript
from ..messages import HostIsNotConnectedError
from ..types import Package
from ..types.rpmver import RPMVersion
from . import Target
from .actions import (
    FileDelete,
    FileDownload,
    FileUpload,
    RunCommand,
    ThreadedMethod,
    queue,
    spinner,
)
from .locks import TargetLockedError

logger = getLogger("mtui.target.hostgroup")


@final
class HostsGroup(UserDict[str, Target]):
    """
    Composite pattern for Dict[hostname, Target]

    doesn't deal with Target state as that would require too much work
    to support properly. so

    1. All the given hosts are expected to be enabled.

    2. Lifetime of the object should be the same as execution of one
       command given from user (to ensure 1.)
    """

    def __init__(self, hosts: list[Target]) -> None:
        """
        :param targets: list of L{Target}
        """
        super().__init__({h.hostname: h for h in hosts})

    def select(
        self, hosts: list[str] | None = None, enabled: bool = False
    ) -> Self | "HostsGroup":
        if not hosts:
            if enabled:
                return HostsGroup(
                    [h for h in self.data.values() if h.state != "disabled"]
                )
            return self

        for x in hosts:
            if x not in self.data:
                raise HostIsNotConnectedError(x)

        return HostsGroup(
            [
                h
                for hn, h in self.data.items()
                if hn in hosts and ((not enabled) or h.state != "disabled")
            ]
        )

    def unlock(self, *a, **kw) -> None:
        for x in self.data.values():
            try:
                x.unlock(*a, **kw)
            except TargetLockedError:
                pass  # logged in Target#unlock

    def lock(self, *a, **kw) -> None:
        for x in self.data.values():
            try:
                x.lock(*a, **kw)
            except TargetLockedError:
                pass

    def query_versions(
        self, packages
    ) -> list[tuple[Target, dict[str, RPMVersion | None]]]:
        rs: list[tuple[Target, dict[str, RPMVersion | None]]] = []
        for x in self.data.values():
            rs.append((x, x.query_package_versions(packages)))
        return rs

    def add_history(self, data) -> None:
        for tgt in self.data.values():
            tgt.add_history(data)

    def names(self) -> list[str]:
        return list(self.data.keys())

    def sftp_get(self, remote: Path, local: Path) -> None:
        return FileDownload(self.data.values(), remote, local).run()

    def sftp_put(self, local: Path, remote: Path) -> None:
        return FileUpload(self.data.values(), local, remote).run()

    def sftp_remove(self, path: Path) -> None:
        return FileDelete(self.data.values(), path).run()

    def run(self, cmd) -> None:
        return self._run(cmd)

    def _run(self, cmd) -> None:
        return RunCommand(self.data, cmd).run()

    def _reboot(self, reboot: dict[str, str]) -> None:
        if reboot:
            logger.info("Rebooting transactional hosts %s", reboot.keys())
            self.run(reboot)
            for hn in reboot.keys():
                self.data[hn].reconnect(retry=5, backoff=True)

    def update_lock(self) -> None:
        try:
            skipped = False
            for t in self.data.values():
                if t.is_locked() and not t._lock.is_mine():
                    skipped = True
                    logger.warning(
                        "host %s is locked since %s by %s. skipping.",
                        t.hostname,
                        t._lock.time(),
                        t._lock.locked_by(),
                    )
                    if t._lock.comment():
                        logger.info(
                            "%s's comment: %s", t._lock.locked_by(), t._lock.comment()
                        )
                else:
                    t.lock()
                    thread = ThreadedMethod(queue)
                    thread.setDaemon(True)
                    thread.start()

            if skipped:
                for t in self.data.values():
                    try:
                        t.unlock()
                    except AssertionError:
                        pass
                raise UpdateError("Hosts locked")
        except BaseException:
            raise

    def perform_install(self, packages: list[str]) -> None:
        commands = {
            t.hostname: t.get_installer()["command"].substitute(
                packages=" ".join(packages)
            )
            for t in self.data.values()
        }
        reboot = {
            t.hostname: t.get_installer()["reboot"].substitute()
            for t in self.data.values()
            if t.transactional
        }
        self.update_lock()
        try:
            self.run(commands)
            for t in self.data.values():
                t.get_installer_check()(
                    t.hostname, t.lastout(), t.lastin(), t.lasterr(), t.lastexit()
                )
            self._reboot(reboot)

        except BaseException:
            raise
        finally:
            self.unlock()

    def perform_uninstall(self, packages: list[str]) -> None:
        commands = {
            t.hostname: t.get_uninstaller()["command"].substitute(
                packages=" ".join(packages)
            )
            for t in self.data.values()
        }
        reboot = {
            t.hostname: t.get_uninstaller()["reboot"].substitute()
            for t in self.data.values()
            if t.transactional
        }
        self.update_lock()
        try:
            self.run(commands)

            for t in self.data.values():
                t.get_uninstaller_check()(
                    t.hostname, t.lastout(), t.lastin(), t.lasterr(), t.lastexit()
                )
            self._reboot(reboot)
        except BaseException:
            raise
        finally:
            self.unlock()

    def perform_prepare(self, packages: list[str], testreport, **kw) -> None:
        operation = "add" if kw.get("testing", False) else "remove"
        force = kw.get("force", False)
        testing = kw.get("testing", False)
        cmd = "installed_only" if kw.get("installed_only", False) else "command"
        pkgs = [p for p in packages if p != "branding-upstream"]
        # big change, all packages prepared in one step, so we dont need reboot transactional systems too many times

        reboot = {
            t.hostname: t.get_preparer()["reboot"].substitute()
            for t in self.data.values()
            if t.transactional
        }
        start = {
            t.hostname: t.get_preparer()["start_command"].substitute()
            for t in self.data.values()
            if t.transactional
        }

        self.update_lock()

        try:
            for t in self.data.values():
                queue.put((t.set_repo, [operation, testreport]))

            while queue.unfinished_tasks:
                spinner()
            if start:
                self.run(start)

            for t in self.data.values():
                if t.lasterr():
                    logger.critical(
                        "Failed to prepare host %s/ Stopping..\n# %s\n%s",
                        t.hostname,
                        t.lastin(),
                        t.lastout(),
                    )
                    return
            for pkg in pkgs:
                command = {
                    t.hostname: t.get_preparer(force, testing)[cmd].substitute(
                        package=pkg
                    )
                    for t in self.data.values()
                }

                self.run(command)

            for t in self.data.values():
                t.get_preparer_check()(
                    t.hostname, t.lastout(), t.lastin(), t.lasterr(), t.lastexit()
                )
            self._reboot(reboot)

        except BaseException:
            pass
        finally:
            self.unlock()

    def perform_downgrade(self, packages: list[str], testreport) -> None:
        ver_re = re.compile(r"(.*) = (.*)")
        versions: dict[str, dict[str, str]] = {}
        self.update_lock()

        reboot = {
            t.hostname: t.get_downgrader()["reboot"].substitute()
            for t in self.data.values()
            if t.transactional
        }
        init_snapshot = {
            t.hostname: t.get_downgrader()["init_snapshot"].substitute()
            for t in self.data.values()
            if t.transactional
        }

        try:
            for t in self.data.values():
                queue.put((t.set_repo, ["remove", testreport]))

            while queue.unfinished_tasks:
                spinner()

            queue.join()

            list_cmd = {
                h: t.get_downgrader()["list_command"].safe_substitute(
                    packages=" ".join(packages)
                )
                for h, t in self.data.items()
                if "list_command" in t.get_downgrader()
            }
            self.run(list_cmd)

            for hn, t in self.data.items():
                lines: list[str] = t.lastout().split("\n")
                release: dict[str, list[str]] = {}

                for line in lines:
                    if match := re.search(ver_re, line):
                        name = match.group(1)
                        version = match.group(2)
                        release.setdefault(name, []).append(version)

                for name in release:
                    version = sorted(release[name], key=RPMVersion, reverse=True)[0]
                    versions.setdefault(hn, dict()).update({name: version})

            if init_snapshot:
                self.run(init_snapshot)

            for package in packages:
                cmd = {
                    h: t.get_downgrader()["command"].safe_substitute(
                        package=package, version=versions[h][package]
                    )
                    for h, t in self.data.items()
                    if package in versions[h]
                }
                if cmd:
                    self.run(cmd)

                    for t in self.data.values():
                        t.get_downgrader_check()(
                            t.hostname,
                            t.lastout(),
                            t.lastin(),
                            t.lasterr(),
                            t.lastexit(),
                        )

            self._reboot(reboot)

        except BaseException:
            raise
        finally:
            self.unlock()

    def perform_update(self, testreport, params: list[str]) -> None:
        def package_check(post: bool = False) -> None:
            for hn, t in self.data.items():
                not_installed: list[Package] = []

                t.query_versions()

                for pkg in t.packages.values():
                    after = None
                    required = pkg.required
                    if not post:
                        before = pkg.current
                        pkg.before = before
                    else:
                        before = pkg.before
                        after = pkg.current

                        pkg.after = after

                    if not before:
                        not_installed.append(pkg)
                    else:
                        if before >= required:  # type: ignore
                            logger.warning(
                                "%s: package is too recent: %s (%s, target version is %s)",
                                hn,
                                pkg,
                                before,
                                required,
                            )

                    if after and before:
                        if before == after:
                            logger.warning(
                                "%s: package was not updated: %s (%s)", hn, pkg, after
                            )
                    if after:
                        if after < required:  # type: ignore
                            logger.warning(
                                "%s: package does not match required version: %s (%s, required %s)",
                                hn,
                                pkg,
                                after,
                                required,
                            )

                if not_installed:
                    logger.warning(
                        "%s: these packages are missing: %s", hn, not_installed
                    )

        if "noprepare" not in params:
            self.perform_prepare(testreport.get_package_list(), testreport)

        package_check()

        if "noscript" not in params and not testreport.config.auto:
            testreport.run_scripts(PreScript, self)

        self.update_lock()

        for t in self.data.values():
            queue.put((t.set_repo, ["add", testreport]))

        while queue.unfinished_tasks:
            spinner()

        queue.join()

        repa = f":p={testreport.rrid.maintenance_id}:{testreport.rrid.review_id}"
        commands = {
            hn: t.get_updater()["command"].safe_substitute(
                repa=repa, packages=" ".join(testreport.get_package_list())
            )
            for hn, t in self.data.items()
        }
        reboot = {
            t.hostname: t.get_updater()["reboot"].substitute()
            for t in self.data.values()
            if t.transactional
        }

        try:
            self.run(commands)
            for t in self.data.values():
                t.get_updater_check()(
                    t.hostname, t.lastout(), t.lastin(), t.lasterr(), t.lastexit()
                )
            self._reboot(reboot)
        except BaseException:
            raise
        finally:
            self.unlock()

        if "newpackage" in params:
            self.perform_prepare(
                testreport.get_package_list(), testreport, testing=True
            )

        package_check(True)

        if "noscript" not in params and not testreport.config.auto:
            testreport.run_scripts(PostScript, self)
            testreport.run_scripts(CompareScript, self)

    def report_self(self, sink):
        for hn in sorted(self.data.keys()):
            self.data[hn].report_self(sink)

    def report_history(self, sink, count, events) -> None:
        if events:
            self._run(
                "tac /var/log/mtui.log | grep -m {} {} | tac".format(
                    count, " ".join([('-e ":{}"'.format(e)) for e in events])
                )
            )
        else:
            self._run(f"tail -n {count} /var/log/mtui.log")

        for hn in sorted(self.data.keys()):
            self.data[hn].report_history(sink)

    def report_locks(self, sink):
        for hn in sorted(self.data.keys()):
            self.data[hn].report_locks(sink)

    def report_timeout(self, sink) -> None:
        for hn in sorted(self.data.keys()):
            self.data[hn].report_timeout(sink)

    def report_sessions(self, sink) -> None:
        for hn in sorted(self.data.keys()):
            self.data[hn].report_sessions(sink)

    def report_log(self, sink, arg) -> None:
        for hn in sorted(self.data.keys()):
            self.data[hn].report_log(sink, arg)

    def report_products(self, sink) -> None:
        for hn in sorted(self.data.keys()):
            self.data[hn].report_products(sink)
