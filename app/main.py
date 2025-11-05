from __future__ import annotations

from pathlib import Path
import sys
from typing import Optional, List

from fastapi import Depends, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, JSONResponse
import json
import requests
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, or_, case
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from .db import engine, get_db
from .models import Base, User, SpeciesReport, ReportStatus, PointsLedger, Donation, DailySignin, QuestLog, ShopItem, Redemption
from .security import hash_password, verify_password
from .utils import MEDIA_ROOT, ensure_media_dirs, save_upload, join_paths, split_paths, delete_media_list
import json as _json


app = FastAPI(title="Komodo Hub Lite")
app.add_middleware(SessionMiddleware, secret_key="dev-secret-change-me")


# Resolve base dir for templates both in dev and frozen bundle
def _base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        # app package placed under extracted temp; include 'app' folder in build
        return Path(getattr(sys, '_MEIPASS', Path.cwd())) / 'app'
    return Path(__file__).resolve().parent

BASE_DIR = _base_dir()
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TAX_CACHE_PATH = DATA_DIR / "tax_cache.json"

POINTS_PER_CNY = 10
SIGNIN_POINTS = 5
QUEST_CONFIG = {
    "view_5": {"title": "浏览 5 张动物卡片", "need": 5, "points": 5},
    "share_1": {"title": "分享 1 次动物卡片", "need": 1, "points": 5},
    "report_1": {"title": "上报 1 条物种", "need": 1, "points": 10},
}


def _highlight(text: str | None, query: str | None) -> str:
    from markupsafe import Markup, escape
    if not text:
        return ""
    if not query:
        return escape(text)
    try:
        q = query.strip()
        if not q:
            return escape(text)
        import re
        pattern = re.compile(re.escape(q), re.IGNORECASE)
        def repl(m):
            return f"<mark>{escape(m.group(0))}</mark>"
        # Escape first, then replace with <mark> by operating on original and re-escaping non-matched parts
        # Simpler approach: split and join
        parts = pattern.split(text)
        matches = pattern.findall(text)
        out = []
        for i, part in enumerate(parts):
            out.append(escape(part))
            if i < len(matches):
                out.append(Markup(f"<mark>{escape(matches[i])}</mark>"))
        return Markup("").join(out)
    except Exception:
        return escape(text)


def _excerpt(text: str | None, query: str | None, radius: int = 80) -> str:
    from markupsafe import Markup, escape
    if not text:
        return ""
    if not query:
        s = text.strip()
        s = s[: radius * 2 + 20] + ("..." if len(s) > radius * 2 + 20 else "")
        return escape(s)
    t_lower = text.lower()
    q = query.strip().lower()
    if not q:
        return escape(text)
    idx = t_lower.find(q)
    if idx == -1:
        s = text.strip()
        s = s[: radius * 2 + 20] + ("..." if len(s) > radius * 2 + 20 else "")
        return escape(s)
    start = max(0, idx - radius)
    end = min(len(text), idx + len(q) + radius)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return _highlight(snippet, query)


templates.env.filters["highlight"] = _highlight
templates.env.filters["excerpt"] = _excerpt

# Ensure English quest titles
QUEST_CONFIG = {
    "view_5": {"title": "View 5 animal cards", "need": 5, "points": 5},
    "share_1": {"title": "Share 1 animal card", "need": 1, "points": 5},
    "report_1": {"title": "Submit 1 species report", "need": 1, "points": 10},
}


# Create tables and media dirs on startup
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_media_dirs()
    _ensure_schema()
    _ensure_seed_shop()


def _ensure_schema():
    """Ensure new taxonomy columns exist (SQLite simple migration)."""
    from sqlalchemy import text

    cols_needed = [
        ("phylum", "TEXT"),
        ("class_name", "TEXT"),
        ("order_name", "TEXT"),
        ("family", "TEXT"),
        ("genus", "TEXT"),
    ]
    with engine.begin() as conn:
        try:
            existing = {row[1] for row in conn.execute(text("PRAGMA table_info(species_reports)"))}
            for col, typ in cols_needed:
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE species_reports ADD COLUMN {col} {typ}"))
        except Exception:
            # Best-effort on non-sqlite or errors; ignore in demo
            pass


def _ensure_seed_shop():
    # seed minimal shop items
    from sqlalchemy import func
    with engine.begin() as conn:
        cnt = conn.execute(select(func.count()).select_from(ShopItem)).scalar()
        if not cnt:
            conn.execute(
                ShopItem.__table__.insert(),
                [
                    {"kind": "virtual", "title": "Official Animal Avatar Pack", "description": "Unlock a set of high-quality animal avatars", "points_cost": 100, "stock": None, "media_url": None, "status": "active"},
                    {"kind": "physical", "title": "Animal Canvas Tote", "description": "Physical merch, shipping required", "points_cost": 5000, "stock": 50, "media_url": None, "status": "active"},
                ],
            )
        # migrate any previous Chinese records to English and ensure cost
        conn.execute(
            ShopItem.__table__.update()
            .where(ShopItem.title == "动物主题帆布袋")
            .values(title="Animal Canvas Tote", description="Physical merch, shipping required", points_cost=5000)
        )
        conn.execute(
            ShopItem.__table__.update()
            .where(ShopItem.title == "官方动物头像包")
            .values(title="Official Animal Avatar Pack", description="Unlock a set of high-quality animal avatars")
        )


def _repair_users_table():
    from sqlalchemy import text
    with engine.begin() as conn:
        try:
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
            wanted = {
                "avatar_url": "TEXT",
                "gender": "TEXT",
                "bio": "TEXT",
                "city": "TEXT",
                "theme": "TEXT",
                "favorites": "TEXT",
                "public_profile": "INTEGER DEFAULT 0",
                "last_active_at": "DATETIME",
            }
            for name, typ in wanted.items():
                if name not in cols:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {typ}"))
        except Exception:
            pass


@app.get("/dev/db/repair")
def dev_db_repair():
    _repair_users_table()
    _ensure_schema()
    return JSONResponse({"status": "ok", "message": "schema ensured"})


ALLOWED_PHYLA = {"Chordata", "Arthropoda", "Mollusca", "Cnidaria", "Echinodermata"}


def _default_taxonomy() -> dict:
    return {
        "Chordata": {
            "Mammalia": {
                "Carnivora": {
                    "Felidae": ["Panthera", "Felis"],
                    "Canidae": ["Canis", "Vulpes"],
                    "Ursidae": ["Ursus"],
                },
                "Primates": {"Hominidae": ["Homo"], "Cercopithecidae": ["Macaca"]},
                "Artiodactyla": {"Cervidae": ["Cervus"]},
                "Perissodactyla": {"Equidae": ["Equus"]},
                "Cetacea": {"Delphinidae": ["Delphinus"], "Balaenopteridae": ["Balaenoptera"]},
            },
            "Aves": {
                "Passeriformes": {"Corvidae": ["Corvus", "Pica"], "Paridae": ["Parus"], "Sittidae": ["Sitta"]},
                "Accipitriformes": {"Accipitridae": ["Aquila", "Buteo"]},
                "Strigiformes": {"Strigidae": ["Strix"], "Tytonidae": ["Tyto"]},
                "Anseriformes": {"Anatidae": ["Anas"]},
            },
            "Reptilia": {
                "Squamata": {"Varanidae": ["Varanus"], "Pythonidae": ["Python"]},
                "Testudines": {"Cheloniidae": ["Chelonia"]},
                "Crocodylia": {"Crocodylidae": ["Crocodylus"]},
            },
            "Amphibia": {"Anura": {"Hylidae": ["Hyla"], "Ranidae": ["Rana"]}, "Caudata": {"Salamandridae": ["Salamandra"]}},
            "Actinopterygii": {"Perciformes": {"Cichlidae": ["Oreochromis"]}},
        },
        "Arthropoda": {
            "Insecta": {
                "Lepidoptera": {"Papilionidae": ["Papilio"], "Nymphalidae": ["Vanessa"]},
                "Coleoptera": {"Carabidae": ["Carabus"], "Coccinellidae": ["Coccinella"]},
                "Hymenoptera": {"Apidae": ["Apis", "Bombus"]},
            },
            "Arachnida": {"Araneae": {"Salticidae": ["Salticus"]}},
            "Crustacea": {"Decapoda": {"Portunidae": ["Portunus"]}},
        },
        "Mollusca": {
            "Gastropoda": {"Stylommatophora": {"Helicidae": ["Helix"]}},
            "Cephalopoda": {"Octopoda": {"Octopodidae": ["Octopus"]}},
            "Bivalvia": {"Venerida": {"Veneridae": ["Ruditapes"]}},
        },
        "Cnidaria": {"Anthozoa": {"Scleractinia": {"Acroporidae": ["Acropora"]}}},
        "Echinodermata": {
            "Asteroidea": {"Valvatida": {"Asteriidae": ["Asterias"]}},
            "Echinoidea": {"Camarodonta": {"Echinidae": ["Paracentrotus"]}},
        },
    }


@app.get("/api/taxonomy")
def get_taxonomy():
    try:
        path = DATA_DIR / "taxonomy.json"
        if path.exists():
            import json
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Filter to allowed phyla only
            filtered = {k: v for k, v in data.items() if k in ALLOWED_PHYLA}
            return JSONResponse(filtered)
    except Exception:
        pass
    # Default already contains only allowed phyla
    return JSONResponse(_default_taxonomy())


# Note: Internationalization removed; site defaults to English text.


def _load_tax_cache() -> dict:
    try:
        if TAX_CACHE_PATH.exists():
            with open(TAX_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_tax_cache(cache: dict) -> None:
    try:
        with open(TAX_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


@app.get("/api/taxonomy/lookup")
def taxonomy_lookup(name: str):
    """Lookup taxonomy (phylum/class/order/family/genus) via Wikidata and cache locally."""
    key = name.strip()
    if not key:
        return JSONResponse({"error": "empty name"}, status_code=400)
    cache = _load_tax_cache()
    hit = cache.get(key.lower())
    if hit:
        return JSONResponse(hit)
    try:
        data = _wikidata_taxonomy(key)
        if data:
            phy = data.get("phylum")
            if phy and phy not in ALLOWED_PHYLA:
                return JSONResponse({"error": "phylum_not_allowed", "phylum": phy}, status_code=422)
            cache[key.lower()] = data
            _save_tax_cache(cache)
            return JSONResponse(data)
        return JSONResponse({"error": "not_found"}, status_code=404)
    except Exception:
        return JSONResponse({"error": "lookup_failed"}, status_code=502)


def _wikidata_taxonomy(species_name: str) -> dict | None:
    """Query Wikidata SPARQL for the taxonomic chain of a species name (wdt:P225 exact match)."""
    endpoint = "https://query.wikidata.org/sparql"
    query = f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?rank ?rankLabel ?ancestorLabel WHERE {{
  ?item wdt:P225 "{species_name}" .
  ?item wdt:P171* ?ancestor .
  ?ancestor wdt:P105 ?rank .
  VALUES ?rank {{ wd:Q38348 wd:Q37517 wd:Q36602 wd:Q35409 wd:Q34740 }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "la,en". }}
}}
    """
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "KomodoHub/1.0 (+https://example.local)"
    }
    resp = requests.get(endpoint, params={"query": query}, headers=headers, timeout=25)
    if resp.status_code != 200:
        return None
    res = resp.json()
    bindings = res.get("results", {}).get("bindings", [])
    rank_map = {"Q38348": "phylum", "Q37517": "class_name", "Q36602": "order_name", "Q35409": "family", "Q34740": "genus"}
    out: dict[str, str] = {}
    for b in bindings:
        rank_uri = b.get("rank", {}).get("value", "")
        rank_id = rank_uri.rsplit("/", 1)[-1]
        label = b.get("ancestorLabel", {}).get("value", "")
        key = rank_map.get(rank_id)
        if key and label and key not in out:
            out[key] = label
    return out or None


# Serve media files
# 允许目录在启动时创建，避免导入阶段校验失败
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT), check_dir=False), name="media")


# Helpers for session-based auth
def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.get(User, uid)


def require_user(user: Optional[User]) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(user: Optional[User]) -> User:
    u = require_user(user)
    if not u.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return u


POINTS_PER_CNY = 10


def award_points(db: Session, user_id: int, delta: int, reason: str, ref_type: str | None = None, ref_id: int | None = None):
    entry = PointsLedger(user_id=user_id, delta=delta, reason=reason, ref_type=ref_type, ref_id=ref_id)
    db.add(entry)
    db.commit()


def get_points_balance(db: Session, user_id: int) -> int:
    from sqlalchemy import func
    total = db.execute(select(func.coalesce(func.sum(PointsLedger.delta), 0)).where(PointsLedger.user_id == user_id)).scalar()
    return int(total or 0)


def award_points(db: Session, user_id: int, delta: int, reason: str, ref_type: str | None = None, ref_id: int | None = None):
    entry = PointsLedger(user_id=user_id, delta=delta, reason=reason, ref_type=ref_type, ref_id=ref_id)
    db.add(entry)
    db.commit()


def _today_str():
    from datetime import datetime
    return datetime.utcnow().strftime("%Y-%m-%d")


def _bump_session_counter(request: Request, key: str, inc: int = 1):
    d = request.session.get("counters") or {}
    today = _today_str()
    if d.get("date") != today:
        d = {"date": today, "views": 0, "shares": 0, "reports": 0}
    d[key] = int(d.get(key, 0)) + inc
    request.session["counters"] = d


def _get_session_counters(request: Request):
    d = request.session.get("counters") or {}
    if d.get("date") != _today_str():
        return {"date": _today_str(), "views": 0, "shares": 0, "reports": 0}
    return d


# Routes
@app.get("/")
def home(request: Request, q: str | None = None, db: Session = Depends(get_db)):
    # taxonomy filters from query
    phylum = request.query_params.get("phylum") or None
    class_name = request.query_params.get("class_name") or None
    order_name = request.query_params.get("order_name") or None
    family = request.query_params.get("family") or None
    genus = request.query_params.get("genus") or None

    stmt = select(SpeciesReport).where(SpeciesReport.status == ReportStatus.approved.value)
    if q:
        stmt = stmt.where(
            or_(
                SpeciesReport.title.ilike(f"%{q}%"),
                SpeciesReport.species_name.ilike(f"%{q}%"),
                SpeciesReport.description.ilike(f"%{q}%"),
            )
        )
    if phylum:
        stmt = stmt.where(SpeciesReport.phylum == phylum)
    if class_name:
        stmt = stmt.where(SpeciesReport.class_name == class_name)
    if order_name:
        stmt = stmt.where(SpeciesReport.order_name == order_name)
    if family:
        stmt = stmt.where(SpeciesReport.family == family)
    if genus:
        stmt = stmt.where(SpeciesReport.genus == genus)
    # ranking: title > species_name > description
    if q:
        pat = f"%{q}%"
        score = (
            case((SpeciesReport.title.ilike(pat), 1), else_=0) * 3
            + case((SpeciesReport.species_name.ilike(pat), 1), else_=0) * 2
            + case((SpeciesReport.description.ilike(pat), 1), else_=0)
        )
        stmt = stmt.order_by(score.desc(), SpeciesReport.created_at.desc())
    else:
        stmt = stmt.order_by(SpeciesReport.created_at.desc())
    items = db.execute(stmt).scalars().all()
    photos_map = {it.id: split_paths(it.photo_paths) for it in items}
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "user": get_current_user(request, db),
            "items": items,
            "q": q or "",
            "photos_map": photos_map,
            "tax": {
                "phylum": phylum or "",
                "class_name": class_name or "",
                "order_name": order_name or "",
                "family": family or "",
                "genus": genus or "",
            },
        },
    )


@app.get("/report/{report_id}")
def report_detail(request: Request, report_id: int, db: Session = Depends(get_db)):
    report = db.get(SpeciesReport, report_id)
    if not report:
        raise HTTPException(404)
    user = get_current_user(request, db)
    if report.status != ReportStatus.approved.value:
        if not user:
            raise HTTPException(403)
        if not (user.is_admin or user.id == report.reporter_id):
            raise HTTPException(403)
    photos = split_paths(report.photo_paths)
    _bump_session_counter(request, "views", 1)
    return templates.TemplateResponse(
        "report_detail.html",
        {"request": request, "user": user, "item": report, "photos": photos},
    )


@app.get("/donate/{report_id}")
def donate_get(request: Request, report_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    rep = db.get(SpeciesReport, report_id)
    if not rep:
        raise HTTPException(404)
    balance = get_points_balance(db, user.id) if user else 0
    return templates.TemplateResponse(
        "donate.html",
        {
            "request": request,
            "user": user,
            "item": rep,
            "points": balance,
            "success": request.query_params.get("ok"),
            "points_per_cny": POINTS_PER_CNY,
        },
    )


@app.post("/donate/{report_id}")
def donate_post(
    request: Request,
    report_id: int,
    amount: str = Form(...),
    db: Session = Depends(get_db),
):
    user = require_user(get_current_user(request, db))
    rep = db.get(SpeciesReport, report_id)
    if not rep:
        raise HTTPException(404)
    try:
        amt = float(amount)
    except Exception:
        return templates.TemplateResponse(
            "donate.html",
            {"request": request, "user": user, "item": rep, "error": "Please enter a valid amount", "points": get_points_balance(db, user.id), "points_per_cny": POINTS_PER_CNY},
            status_code=400,
        )
    if amt <= 0:
        return templates.TemplateResponse(
            "donate.html",
            {"request": request, "user": user, "item": rep, "error": "Amount must be greater than 0", "points": get_points_balance(db, user.id), "points_per_cny": POINTS_PER_CNY},
            status_code=400,
        )
    cents = int(round(amt * 100))
    don = Donation(user_id=user.id, report_id=rep.id, species_name=rep.species_name, amount_cents=cents, currency="CNY", provider="alipay", status="paid")
    db.add(don)
    db.commit()
    db.refresh(don)
    # award points
    pts = int(amt * POINTS_PER_CNY)
    award_points(db, user.id, pts, reason="donate", ref_type="donation", ref_id=don.id)
    return RedirectResponse(f"/donate/{rep.id}?ok=1", status_code=303)


@app.get("/share/{report_id}")
def share_report(request: Request, report_id: int, db: Session = Depends(get_db)):
    rep = db.get(SpeciesReport, report_id)
    if not rep:
        raise HTTPException(404)
    _bump_session_counter(request, "shares", 1)
    url = request.url_for("report_detail", report_id=report_id)
    return templates.TemplateResponse("share.html", {"request": request, "item": rep, "share_url": str(url)})


@app.get("/points")
def points_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(get_current_user(request, db))
    balance = get_points_balance(db, user.id)
    counters = _get_session_counters(request)
    quests = []
    today = _today_str()
    for code, cfg in QUEST_CONFIG.items():
        progress = counters["views"] if code == "view_5" else counters["shares"] if code == "share_1" else counters["reports"]
        done = progress >= cfg["need"]
        ql = db.execute(select(QuestLog).where(QuestLog.user_id == user.id, QuestLog.code == code, QuestLog.date == today)).scalar_one_or_none()
        rewarded = bool(ql and ql.rewarded)
        quests.append({"code": code, "title": cfg["title"], "need": cfg["need"], "points": cfg["points"], "progress": progress, "done": done, "rewarded": rewarded})
    recent = db.execute(select(PointsLedger).where(PointsLedger.user_id == user.id).order_by(PointsLedger.created_at.desc()).limit(20)).scalars().all()
    signed = db.execute(select(DailySignin).where(DailySignin.user_id == user.id, DailySignin.date == today)).scalar_one_or_none()
    return templates.TemplateResponse("points.html", {"request": request, "user": user, "balance": balance, "quests": quests, "recent": recent, "signed": bool(signed), "signin_points": SIGNIN_POINTS})


@app.post("/points/signin")
def points_signin(request: Request, db: Session = Depends(get_db)):
    user = require_user(get_current_user(request, db))
    today = _today_str()
    exists = db.execute(select(DailySignin).where(DailySignin.user_id == user.id, DailySignin.date == today)).scalar_one_or_none()
    if exists:
        return RedirectResponse("/points", status_code=303)
    ds = DailySignin(user_id=user.id, date=today, points=SIGNIN_POINTS)
    db.add(ds)
    db.commit()
    award_points(db, user.id, SIGNIN_POINTS, reason="signin", ref_type="daily", ref_id=ds.id)
    return RedirectResponse("/points", status_code=303)


@app.post("/points/quests/{code}/claim")
def quest_claim(request: Request, code: str, db: Session = Depends(get_db)):
    user = require_user(get_current_user(request, db))
    cfg = QUEST_CONFIG.get(code)
    if not cfg:
        raise HTTPException(404)
    counters = _get_session_counters(request)
    progress = counters["views"] if code == "view_5" else counters["shares"] if code == "share_1" else counters["reports"]
    if progress < cfg["need"]:
        return RedirectResponse("/points", status_code=303)
    today = _today_str()
    ql = db.execute(select(QuestLog).where(QuestLog.user_id == user.id, QuestLog.code == code, QuestLog.date == today)).scalar_one_or_none()
    if ql and ql.rewarded:
        return RedirectResponse("/points", status_code=303)
    if not ql:
        ql = QuestLog(user_id=user.id, code=code, date=today, progress=progress, completed=True, rewarded=False)
        db.add(ql)
        db.commit()
        db.refresh(ql)
    ql.rewarded = True
    db.add(ql)
    db.commit()
    award_points(db, user.id, cfg["points"], reason="quest", ref_type="quest", ref_id=ql.id)
    return RedirectResponse("/points", status_code=303)


@app.get("/shop")
def shop_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(get_current_user(request, db))
    balance = get_points_balance(db, user.id)
    items = db.execute(select(ShopItem).where(ShopItem.status == "active")).scalars().all()
    return templates.TemplateResponse("shop.html", {"request": request, "user": user, "balance": balance, "items": items})


@app.post("/shop/redeem/{item_id}")
def shop_redeem(request: Request, item_id: int, shipping_text: str = Form(""), db: Session = Depends(get_db)):
    user = require_user(get_current_user(request, db))
    item = db.get(ShopItem, item_id)
    if not item or item.status != "active":
        raise HTTPException(404)
    balance = get_points_balance(db, user.id)
    if balance < item.points_cost:
        items = db.execute(select(ShopItem).where(ShopItem.status == "active")).scalars().all()
        return templates.TemplateResponse("shop.html", {"request": request, "user": user, "balance": balance, "items": items, "error": "Insufficient points"}, status_code=400)
    if item.stock is not None and item.stock <= 0:
        items = db.execute(select(ShopItem).where(ShopItem.status == "active")).scalars().all()
        return templates.TemplateResponse("shop.html", {"request": request, "user": user, "balance": balance, "items": items, "error": "Out of stock"}, status_code=400)
    red = Redemption(user_id=user.id, item_id=item.id, points_cost=item.points_cost, status="pending", shipping_text=shipping_text.strip() or None)
    db.add(red)
    db.commit()
    db.refresh(red)
    award_points(db, user.id, -item.points_cost, reason="redeem", ref_type="redemption", ref_id=red.id)
    if item.stock is not None:
        item.stock -= 1
        db.add(item)
        db.commit()
    return RedirectResponse("/shop", status_code=303)


@app.get("/register")
def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register_post(
    request: Request,
    email: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already registered", "email": email, "display_name": display_name},
            status_code=400,
        )
    u = User(email=email, display_name=display_name.strip(), password_hash=hash_password(password))
    db.add(u)
    db.commit()
    db.refresh(u)
    request.session["user_id"] = u.id
    return RedirectResponse("/", status_code=303)


@app.get("/login")
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid credentials", "email": email}, status_code=400
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/profile")
def profile_get(request: Request, db: Session = Depends(get_db)):
    user = require_user(get_current_user(request, db))
    total_reports = db.execute(select(SpeciesReport).where(SpeciesReport.reporter_id == user.id)).scalars().all()
    approved = [r for r in total_reports if r.status == ReportStatus.approved.value]
    donations = db.execute(select(Donation).where(Donation.user_id == user.id)).scalars().all()
    donations_sum = sum(d.amount_cents for d in donations) / 100.0
    points = get_points_balance(db, user.id)
    favs = []
    if user.favorites:
        try:
            favs = _json.loads(user.favorites)
        except Exception:
            favs = []
    favs_json = _json.dumps(favs, ensure_ascii=False)
    data = {"total_reports": len(total_reports), "approved_reports": len(approved), "donations_sum": donations_sum, "points": points}
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "stats": data, "favs": favs, "favs_json": favs_json})


@app.post("/profile")
async def profile_post(
    request: Request,
    display_name: str = Form(...),
    gender: str = Form(""),
    bio: str = Form(""),
    city: str = Form(""),
    theme: str = Form("light"),
    public_profile: str = Form(""),
    favorites_json: str = Form(""),
    avatar: Optional[UploadFile] = None,
    db: Session = Depends(get_db),
):
    user = require_user(get_current_user(request, db))
    user.display_name = display_name.strip() or user.display_name
    user.gender = (gender or None)
    user.bio = (bio.strip() or None)
    user.city = (city.strip() or None)
    user.theme = (theme or None)
    user.public_profile = True if public_profile == "on" else False
    if favorites_json:
        try:
            favs = _json.loads(favorites_json)
            if isinstance(favs, list):
                favs = favs[:10]
                user.favorites = _json.dumps(favs, ensure_ascii=False)
        except Exception:
            pass
    if avatar and avatar.filename:
        try:
            p = save_upload(avatar, subdir="avatars")
            user.avatar_url = p
        except ValueError as e:
            return templates.TemplateResponse("profile.html", {"request": request, "user": user, "error": str(e)}, status_code=400)
    db.add(user)
    db.commit()
    return RedirectResponse("/profile", status_code=303)



@app.post("/profile/favorites/add/{report_id}")
def add_favorite_from_report(request: Request, report_id: int, db: Session = Depends(get_db)):
    user = require_user(get_current_user(request, db))
    rep = db.get(SpeciesReport, report_id)
    if not rep or rep.reporter_id != user.id:
        raise HTTPException(404)
    entry = {"phylum": rep.phylum, "class_name": rep.class_name, "order_name": rep.order_name, "family": rep.family, "genus": rep.genus, "species": rep.species_name}
    favs = []
    if user.favorites:
        try:
            favs = _json.loads(user.favorites)
        except Exception:
            favs = []
    keys = {(f.get("species") or "").lower() for f in favs}
    if (rep.species_name or "").lower() not in keys:
        favs.insert(0, entry)
        favs = favs[:10]
        user.favorites = _json.dumps(favs, ensure_ascii=False)
        db.add(user)
        db.commit()
    return RedirectResponse("/my/reports", status_code=303)


@app.get("/reports/new")
def new_report_get(request: Request, db: Session = Depends(get_db)):
    user = require_user(get_current_user(request, db))
    return templates.TemplateResponse("new_report.html", {"request": request, "user": user})


@app.post("/reports")
async def create_report(
    request: Request,
    title: str = Form(...),
    species_name: str = Form(...),
    description: str = Form(""),
    location_text: str = Form(""),
    phylum: str = Form(""),
    class_name: str = Form(""),
    order_name: str = Form(""),
    family: str = Form(""),
    genus: str = Form(""),
    photo1: Optional[UploadFile] = None,
    photo2: Optional[UploadFile] = None,
    photo3: Optional[UploadFile] = None,
    db: Session = Depends(get_db),
):
    user = require_user(get_current_user(request, db))
    paths = []
    for f in (photo1, photo2, photo3):
        if f and f.filename:
            try:
                p = save_upload(f)
                paths.append(p)
            except ValueError as e:
                return templates.TemplateResponse(
                    "new_report.html",
                    {"request": request, "user": user, "error": str(e), "title": title, "species_name": species_name, "description": description, "location_text": location_text},
                    status_code=400,
                )

    if not paths:
        return templates.TemplateResponse(
            "new_report.html",
            {
                "request": request,
                "user": user,
                "error": "Please upload at least one image",
                "title": title,
                "species_name": species_name,
                "description": description,
                "location_text": location_text,
            },
            status_code=400,
        )

    # validate phylum if provided
    phy_clean = phylum.strip() if phylum else ""
    if phy_clean and phy_clean not in ALLOWED_PHYLA:
        return templates.TemplateResponse(
            "new_report.html",
            {
                "request": request,
                "user": user,
                "error": "Only these phyla are allowed: Chordata / Arthropoda / Mollusca / Cnidaria / Echinodermata",
                "title": title,
                "species_name": species_name,
                "description": description,
                "location_text": location_text,
            },
            status_code=400,
        )

    rep = SpeciesReport(
        reporter_id=user.id,
        title=title.strip(),
        species_name=species_name.strip(),
        description=description.strip(),
        location_text=location_text.strip(),
        phylum=(phy_clean or None),
        class_name=(class_name.strip() or None),
        order_name=(order_name.strip() or None),
        family=(family.strip() or None),
        genus=(genus.strip() or None),
        photo_paths=join_paths(paths),
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)
    _bump_session_counter(request, "reports", 1)
    return RedirectResponse(f"/report/{rep.id}", status_code=303)


@app.get("/my/reports")
def my_reports(request: Request, db: Session = Depends(get_db)):
    user = require_user(get_current_user(request, db))
    items = (
        db.execute(
            select(SpeciesReport).where(SpeciesReport.reporter_id == user.id).order_by(SpeciesReport.created_at.desc())
        ).scalars().all()
    )
    return templates.TemplateResponse("my_reports.html", {"request": request, "user": user, "items": items})


@app.get("/admin/reports")
def admin_reports(request: Request, status: str = "pending", db: Session = Depends(get_db)):
    admin = require_admin(get_current_user(request, db))
    if status not in {s.value for s in ReportStatus}:
        status = "pending"
    items = (
        db.execute(
            select(SpeciesReport).where(SpeciesReport.status == status).order_by(SpeciesReport.created_at.desc())
        ).scalars().all()
    )
    return templates.TemplateResponse(
        "admin_reports.html", {"request": request, "user": admin, "items": items, "status": status}
    )


@app.post("/admin/reports/{report_id}/review")
def review_report(
    request: Request,
    report_id: int,
    action: str = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = require_admin(get_current_user(request, db))
    rep = db.get(SpeciesReport, report_id)
    if not rep:
        raise HTTPException(404)
    valid_actions = {"approve", "reject", "revoke", "pending"}
    if action not in valid_actions:
        raise HTTPException(400, detail="Invalid action")

    if action == "approve":
        rep.status = ReportStatus.approved.value
        rep.reviewed_by = admin.id
    elif action == "reject":
        rep.status = ReportStatus.rejected.value
        rep.reviewed_by = admin.id
    elif action == "revoke":
        # Move approved → rejected
        rep.status = ReportStatus.rejected.value
        rep.reviewed_by = admin.id
    elif action == "pending":
        # Move rejected → pending
        rep.status = ReportStatus.pending.value
        rep.reviewed_by = None

    rep.review_note = note.strip() or None
    db.add(rep)
    db.commit()
    return RedirectResponse("/admin/reports?status=pending", status_code=303)


@app.get("/admin/reports/{report_id}/edit")
def edit_report_get(request: Request, report_id: int, db: Session = Depends(get_db)):
    admin = require_admin(get_current_user(request, db))
    rep = db.get(SpeciesReport, report_id)
    if not rep:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "admin_report_edit.html",
        {"request": request, "user": admin, "item": rep, "photos": split_paths(rep.photo_paths)},
    )


@app.post("/admin/reports/{report_id}/edit")
def edit_report_post(
    request: Request,
    report_id: int,
    title: str = Form(...),
    species_name: str = Form(...),
    description: str = Form(""),
    location_text: str = Form(""),
    delete_photos: List[str] = Form([]),
    photo1: Optional[UploadFile] = None,
    photo2: Optional[UploadFile] = None,
    photo3: Optional[UploadFile] = None,
    db: Session = Depends(get_db),
):
    admin = require_admin(get_current_user(request, db))
    rep = db.get(SpeciesReport, report_id)
    if not rep:
        raise HTTPException(404)
    rep.title = title.strip()
    rep.species_name = species_name.strip()
    rep.description = description.strip()
    rep.location_text = location_text.strip()
    # handle optional new photos to append
    paths = []
    for f in (photo1, photo2, photo3):
        if f and f.filename:
            try:
                p = save_upload(f)
                paths.append(p)
            except ValueError as e:
                return templates.TemplateResponse(
                    "admin_report_edit.html",
                    {
                        "request": request,
                        "user": admin,
                        "item": rep,
                        "photos": split_paths(rep.photo_paths),
                        "error": str(e),
                    },
                    status_code=400,
                )
    # compute final photos: remove selected, then append new ones
    existing = split_paths(rep.photo_paths)
    if delete_photos:
        existing = [p for p in existing if p not in set(delete_photos)]
    if paths:
        existing.extend(paths)
    rep.photo_paths = join_paths(existing)
    db.add(rep)
    db.commit()
    return RedirectResponse("/admin/reports?status=pending", status_code=303)


@app.post("/admin/reports/{report_id}/delete")
def delete_report(request: Request, report_id: int, db: Session = Depends(get_db)):
    admin = require_admin(get_current_user(request, db))
    rep = db.get(SpeciesReport, report_id)
    if not rep:
        raise HTTPException(404)
    if rep.status != ReportStatus.rejected.value:
        raise HTTPException(400, detail="Only rejected reports can be deleted")
    # delete media files
    delete_media_list(split_paths(rep.photo_paths))
    db.delete(rep)
    db.commit()
    return RedirectResponse("/admin/reports?status=rejected", status_code=303)


@app.post("/admin/reports/batch")
def batch_reports(
    request: Request,
    action: str = Form(...),
    ids: List[int] = Form([]),
    note: str = Form(""),
    redirect_status: str = Form("pending"),
    db: Session = Depends(get_db),
):
    admin = require_admin(get_current_user(request, db))
    valid_actions = {"approve", "reject", "revoke", "pending", "delete"}
    if action not in valid_actions:
        raise HTTPException(400, detail="Invalid action")
    if not ids:
        return RedirectResponse(f"/admin/reports?status={redirect_status}", status_code=303)

    reps = db.execute(select(SpeciesReport).where(SpeciesReport.id.in_(ids))).scalars().all()
    for rep in reps:
        if action == "approve" and rep.status == ReportStatus.pending.value:
            rep.status = ReportStatus.approved.value
            rep.reviewed_by = admin.id
            rep.review_note = note.strip() or rep.review_note
            db.add(rep)
        elif action == "reject" and rep.status == ReportStatus.pending.value:
            rep.status = ReportStatus.rejected.value
            rep.reviewed_by = admin.id
            rep.review_note = note.strip() or rep.review_note
            db.add(rep)
        elif action == "revoke" and rep.status == ReportStatus.approved.value:
            rep.status = ReportStatus.rejected.value
            rep.reviewed_by = admin.id
            rep.review_note = note.strip() or rep.review_note
            db.add(rep)
        elif action == "pending" and rep.status == ReportStatus.rejected.value:
            rep.status = ReportStatus.pending.value
            rep.reviewed_by = None
            rep.review_note = note.strip() or rep.review_note
            db.add(rep)
        elif action == "delete" and rep.status == ReportStatus.rejected.value:
            delete_media_list(split_paths(rep.photo_paths))
            db.delete(rep)
    db.commit()
    return RedirectResponse(f"/admin/reports?status={redirect_status}", status_code=303)
