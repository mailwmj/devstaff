"""Loopback-only preview; serves web assets, never project records or symlinks."""
import argparse
import functools
import http.server
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Handler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        root = Path(self.directory).resolve()
        parts = Path(unquote(urlsplit(self.path).path).lstrip('/')).parts
        candidate = root.joinpath(*parts)
        if any(p.startswith('.') for p in parts) or any(root.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts) + 1)):
            self.send_error(403)
            return None
        if not candidate.resolve().is_relative_to(root):
            self.send_error(403)
            return None
        if candidate.is_dir() and ((candidate / 'index.html').is_symlink() or not (candidate / 'index.html').is_file()):
            self.send_error(403)
            return None
        return super().send_head()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    state = json.loads((root / '.site/state.json').read_text(encoding='utf-8'))
    port = args.port if args.port is not None else state['runtime']['port']
    if not 0 <= port <= 65535:
        parser.error('Invalid port')
    web = root / 'web'
    if not web.is_dir() or web.is_symlink():
        parser.error('Missing regular web directory')
    try:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', port), functools.partial(Handler, directory=str(web)))
    except OSError as exc:
        parser.exit(1, f'Cannot start preview: {exc}. Preserve the saved origin for browser data; do not kill an unrelated process.\n')
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'project_id': state['project_id']}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
