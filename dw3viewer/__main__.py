"""python -m dw3viewer            desktop window
python -m dw3viewer --serve      local server only (prints its address; for tests and a browser)"""
import sys


def main():
    if '--serve' in sys.argv:
        from .server import API, make_server
        data = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--data=')), None)
        srv = make_server(API(data_dir=data))
        print(srv.url, flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    from .desktop import main as desktop
    return desktop(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
