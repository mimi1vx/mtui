from os.path import join
from xdg.BaseDirectory import save_cache_path as x_save_cache_path  # type: ignore

app = "mtui"


def save_cache_path(*args: str) -> str:
    return join(x_save_cache_path(app), *args)
