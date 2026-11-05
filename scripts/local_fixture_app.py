"""Controlled local application for the TestLab UI regression; never expose externally."""

from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse


app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/auth/login", response_class=HTMLResponse)
def login():
    return ('<main><h1>Fixture login</h1><form action="/auth/session" method="post">'
            '<label>Email<input id="login_email" name="email"></label>'
            '<label>Password<input id="login_password" name="password" type="password"></label>'
            '<button type="submit">Enter</button></form></main>')


@app.post("/auth/session")
async def session(request: Request):
    form = parse_qs((await request.body()).decode("utf-8"))
    if form.get("email") != ["fixture@example.test"] or form.get("password") != ["fixture-only-password"]:
        return HTMLResponse("Denied", status_code=401)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie("fixture_session", "authorized", httponly=True, samesite="strict")
    return response


def _authorized(request: Request) -> bool:
    return request.cookies.get("fixture_session") == "authorized"


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    if not _authorized(request):
        return RedirectResponse("/auth/login")
    return ('<main data-module="Admin" style="background:#17406d;color:white;padding:30px">'
            '<h1>Fixture administration</h1><nav>'
            '<a href="/healthy">Healthy</a> <a href="/js-error">JavaScript</a> '
            '<a href="/server-error">Server</a> <a href="/broken">Broken</a>'
            '</nav></main>')


@app.get("/healthy", response_class=HTMLResponse)
def healthy():
    return '<main data-module="Healthy" style="background:#26875f;padding:30px"><h1>Healthy module</h1><p>All good</p></main>'


@app.get("/js-error", response_class=HTMLResponse)
def js_error():
    return '<main data-module="Scripts" style="background:#e0a243;padding:30px"><h1>Script module</h1><script>throw new Error("fixture intentional")</script></main>'


@app.get("/server-error")
def server_error():
    return HTMLResponse('<main data-module="Server"><h1>Server module</h1></main>', status_code=500)


@app.get("/broken")
def broken():
    return HTMLResponse('<main data-module="Broken"><h1>Broken link</h1></main>', status_code=404)


@app.get("/favicon.ico")
def favicon():
    return HTMLResponse("", status_code=204)
