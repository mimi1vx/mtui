from mtui.argparse import ArgumentParser
from mtui.commands import Command
from mtui.utils import complete_choices


class ListProducts(Command):
    """
    Prints installed products on refhosts.
    """

    command = "list_products"

    @classmethod
    def _add_arguments(cls, parser: ArgumentParser) -> None:
        cls._add_hosts_arg(parser)

    def __call__(self) -> None:
        targets = self.parse_hosts(enabled=False)
        targets.report_products(self.display.list_products)

    @staticmethod
    def complete(state, text, line, begidx, endidx) -> list[str]:
        return complete_choices(
            [("-t", "--target")], line, text, state["hosts"].names()
        )
