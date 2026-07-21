# Battle Cats Save File Editor API

High-Performance Battle Cats Save Customization and Cloud Sync REST API Engine.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-000000.svg)](https://flask.palletsprojects.com/)
[![Vercel](https://img.shields.io/badge/Vercel-Deployed-success.svg)](https://vercel.com/)
[![License: GPL--3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

---

## Key Features

- **Direct Binary Patching Engine**: Avoids deserialization loss/corruptions on newer game versions. Fixes in-game crash issues.
- **Cloud Transfer Integration**: Connects directly to PONOS transfer servers to pull save files, apply modifications, and re-issue new transfer codes and PINs.
- **Extensible JSON API Schema**: Structured JSON endpoints (`POST /edit`, `POST /info`, `POST /max`) for clean scalability.
- **Multi-Item Editing**: Supports Cat Food, XP, Rare Tickets, Platinum Tickets, and Legend Tickets.
- **Interactive Swagger Docs**: Built-in Swagger UI for testing API endpoints directly from your browser.
- **CMD Interactive Client**: Simple, menu-driven CLI client (`cli.py`) for command line usage.

---

## Repository Structure

```text
bcsfe-api/
├── main.py            # Flask REST Server and Route definitions
├── patcher.py         # Binary patcher and PONOS transfer logic engine
├── cli.py             # Interactive CMD Client for end-users
├── vercel.json        # Vercel serverless deployment specification
├── wsgi.py            # WSGI configuration
├── requirements.txt   # Production dependencies
├── DOCS.md            # Detailed API documentation
├── .gitignore         # Environment and temporary save file ignores
├── LICENSE            # GNU General Public License v3.0 (GPL-3.0)
└── README.md          # Documentation and usage guide
```

---

## Quick Start (Live API)

- **Interactive Swagger UI**: `https://battle-cats-save-file-editor-api.vercel.app/docs`
- **Health Check Endpoint**: `https://battle-cats-save-file-editor-api.vercel.app/`

For full API endpoint specifications, refer to [DOCS.md](DOCS.md).

---

## Credits & Acknowledgments

This project builds upon and utilizes the [bcsfe](https://github.com/fieryhenry/BCSFE-Python) library developed by **fieryhenry**. 
- Core save data parsing, cryptographic algorithms, and PONOS transfer protocol handlers are powered by the official `bcsfe` engine.
- Interactive CLI workflow (`cli.py`) is modeled after the original `BCSFE-Python` user interface structure.

---

## License and Disclaimer

Distributed under the **GNU General Public License v3.0 (GPL-3.0)**. See `LICENSE` for more information.

> **Disclaimer**: This tool is developed strictly for educational, research, and reverse engineering testing purposes. Users are solely responsible for compliance with third-party Terms of Service.
