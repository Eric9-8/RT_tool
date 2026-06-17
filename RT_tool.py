from backend.app.main import app


def main() -> None:
    import os

    import uvicorn

    host = os.environ.get("BACKEND_HOST", "0.0.0.0")
    port = int(os.environ.get("BACKEND_PORT", "8000"))
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
