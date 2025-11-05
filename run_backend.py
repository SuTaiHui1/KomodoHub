import sys
import os
from pathlib import Path
from uvicorn import Config, Server


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18555
    # Ensure working directory for bundled/frozen app
    if getattr(sys, 'frozen', False):
        base = Path(getattr(sys, '_MEIPASS', Path(os.getcwd())))
        os.chdir(base)
    else:
        os.chdir(Path(__file__).resolve().parent)
    config = Config("app.main:app", host="127.0.0.1", port=port, reload=False, log_level="info")
    server = Server(config)
    server.run()


if __name__ == "__main__":
    main()
