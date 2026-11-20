import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from apps.inthub_api.server import make_handler


def _boom(*_args, **_kwargs):
    raise RuntimeError("boom")


def _status_and_body(url):
    with pytest.raises(HTTPError) as failure:
        urlopen(url)
    return failure.value.code, failure.value.headers, failure.value.read().decode("utf-8")


def test_a_crash_shows_people_the_500_page_and_keeps_json_for_the_api(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(str(tmp_path / "inthub.db"), serve_web=True))
    handler = server.RequestHandlerClass
    handler._serve_web = _boom
    handler._route_get = _boom
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        status, headers, page = _status_and_body(f"{base}/flow")
        assert status == 500 and headers["Content-Type"].startswith("text/html")
        assert "Something went wrong" in page and "IntHub 这边出了问题" in page
        assert 'href="/"' in page and "__REV__" not in page and "boom" not in page

        status, headers, payload = _status_and_body(f"{base}/api/v1/projects")
        assert status == 500 and headers["Content-Type"].startswith("application/json")
        assert json.loads(payload)["error"]["code"] == "INTERNAL_ERROR" and "boom" not in payload
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
