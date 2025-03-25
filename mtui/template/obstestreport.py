from ..parsemeta import MetadataParser, ReducedMetadataParser
from ..parsemetajson import JSONParser
from ..target import Target
from ..target.hostgroup import HostsGroup
from ..template.repoparse import repoparse
from ..template.testreport import TestReport
from ..types import Product, RequestReviewID


class OBSTestReport(TestReport):
    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)

        self.rrid: RequestReviewID
        self.rating = ""

        self._attrs += [
            "rrid",
            "rating",
        ]

    @property
    def _type(self) -> str:
        return "OBS"

    @property
    def id(self) -> str:
        return str(self.rrid)

    def _parser(self):
        parsers = {
            "full": MetadataParser,
            "hosts": ReducedMetadataParser,
            "json": JSONParser,
        }
        return parsers

    def _update_repos_parser(self) -> dict[Product, str]:
        # TODO: exceptions handling
        return repoparse(self.report_wd())

    def _show_yourself_data(self) -> list[tuple[str, str]]:
        return [
            ("ReviewRequestID", str(self.rrid)),
            ("Rating", self.rating),
        ] + super()._show_yourself_data()

    def set_repo(self, target: Target, operation: str) -> None:
        if operation == "add":
            target.run_zypper("-n ar -ckn", self.update_repos, self.rrid)
        elif operation == "remove":
            target.run_zypper("-n rr", self.update_repos, self.rrid)
        else:
            raise ValueError("Not supported repose operation {}".format(operation))

    def list_update_commands(self, targets: HostsGroup, display) -> None:
        packages = self.get_package_list()
        repa = f":p={self.rrid.maintenance_id}"
        for hn, t in targets.items():
            display(
                f"{hn} - commands: \n{t.get_updater()['command'].safe_substitute(repa=repa, packages=packages)}"
            )
