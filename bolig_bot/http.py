import requests

from .config import TIMEOUT, USER_AGENT
from .models import SourceError


def get(url: str, **kwargs) -> requests.Response:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as e:
        raise SourceError(f"Netværksfejl mod {url}: {e.__class__.__name__}") from e
    if r.status_code != 200:
        raise SourceError(f"HTTP {r.status_code} fra {url}")
    return r
