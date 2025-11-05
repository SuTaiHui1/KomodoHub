import io
import os
import base64
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Set

import requests
from pathlib import Path
import sys


BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_UA = os.environ.get(
    "APP_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 KomodoHub/1.0",
)


@dataclass
class ReportItem:
    title: str
    species_name: str
    description: str
    location_text: str
    phylum: str
    class_name: str
    order_name: str
    family: str
    genus: str
    photo_url: Optional[str] = None


REPORTS: List[ReportItem] = [
    # Mammals
    ReportItem("Lion in savanna", "Panthera leo", "Adult lion resting under acacia shade.", "Serengeti, Tanzania", "Chordata", "Mammalia", "Carnivora", "Felidae", "Panthera"),
    ReportItem("Tiger footprints near forest edge", "Panthera tigris", "Fresh footprints and scratch marks on a tree.", "Sundarbans, India", "Chordata", "Mammalia", "Carnivora", "Felidae", "Panthera"),
    ReportItem("Leopard on tree branch", "Panthera pardus", "Leopard resting on a tree.", "Kruger, South Africa", "Chordata", "Mammalia", "Carnivora", "Felidae", "Panthera"),
    ReportItem("House cat near garden", "Felis catus", "Domestic cat watching birds.", "Neighborhood garden", "Chordata", "Mammalia", "Carnivora", "Felidae", "Felis"),
    ReportItem("Wolf howling at dusk", "Canis lupus", "Gray wolf howling from a ridge.", "Yellowstone, USA", "Chordata", "Mammalia", "Carnivora", "Canidae", "Canis"),
    ReportItem("Coyote crossing trail", "Canis latrans", "Coyote trotting across dirt path.", "Arizona, USA", "Chordata", "Mammalia", "Carnivora", "Canidae", "Canis"),
    ReportItem("Red fox near field", "Vulpes vulpes", "Red fox moving along field edge.", "Normandy, France", "Chordata", "Mammalia", "Carnivora", "Canidae", "Vulpes"),
    ReportItem("Brown bear by river", "Ursus arctos", "Bear fishing in shallow water.", "Kamchatka, Russia", "Chordata", "Mammalia", "Carnivora", "Ursidae", "Ursus"),
    ReportItem("Wild horse herd", "Equus caballus", "Small herd of horses grazing.", "Mongolian steppe", "Chordata", "Mammalia", "Perissodactyla", "Equidae", "Equus"),
    ReportItem("Red deer stag", "Cervus elaphus", "Stag with antlers in meadow.", "Highlands, Scotland", "Chordata", "Mammalia", "Artiodactyla", "Cervidae", "Cervus"),

    # Birds
    ReportItem("Raven calling over cliff", "Corvus corax", "Large raven circling and calling.", "Grand Canyon, USA", "Chordata", "Aves", "Passeriformes", "Corvidae", "Corvus"),
    ReportItem("Eurasian magpie in park", "Pica pica", "Magpie hopping across grass.", "City park", "Chordata", "Aves", "Passeriformes", "Corvidae", "Pica"),
    ReportItem("Great tit at feeder", "Parus major", "Great tit feeding on seeds.", "Backyard, Germany", "Chordata", "Aves", "Passeriformes", "Paridae", "Parus"),
    ReportItem("Golden eagle soaring", "Aquila chrysaetos", "Golden eagle gliding on thermals.", "Highlands, Scotland", "Chordata", "Aves", "Accipitriformes", "Accipitridae", "Aquila"),
    ReportItem("Common buzzard overhead", "Buteo buteo", "Broad-winged buzzard circling.", "Countryside, UK", "Chordata", "Aves", "Accipitriformes", "Accipitridae", "Buteo"),
    ReportItem("Tawny owl at dusk", "Strix aluco", "Owl perched on branch at dusk.", "Woodland edge", "Chordata", "Aves", "Strigiformes", "Strigidae", "Strix"),
    ReportItem("Barn owl over field", "Tyto alba", "Barn owl quartering over field.", "Farmland, Spain", "Chordata", "Aves", "Strigiformes", "Tytonidae", "Tyto"),
    ReportItem("Mallard pair on pond", "Anas platyrhynchos", "Male and female swimming.", "City pond", "Chordata", "Aves", "Anseriformes", "Anatidae", "Anas"),

    # Reptiles & Amphibians
    ReportItem("Komodo dragon sighting", "Varanus komodoensis", "Large monitor lizard basking near trail.", "Komodo NP, Indonesia", "Chordata", "Reptilia", "Squamata", "Varanidae", "Varanus"),
    ReportItem("Ball python coiled", "Python regius", "Royal python resting in coils.", "Captive display", "Chordata", "Reptilia", "Squamata", "Pythonidae", "Python"),
    ReportItem("Green tree frog", "Hyla cinerea", "Green tree frog calling after rain.", "Wetlands, USA", "Chordata", "Amphibia", "Anura", "Hylidae", "Hyla"),
    ReportItem("Common frog by stream", "Rana temporaria", "Brown frog near stream bank.", "Alpine meadow", "Chordata", "Amphibia", "Anura", "Ranidae", "Rana"),

    # Insects
    ReportItem("Swallowtail butterfly on flowers", "Papilio machaon", "Yellow-black swallowtail on purple flowers.", "Provence, France", "Arthropoda", "Insecta", "Lepidoptera", "Papilionidae", "Papilio"),
    ReportItem("Red admiral butterfly", "Vanessa atalanta", "Butterfly basking with wings open.", "Hedgerow, UK", "Arthropoda", "Insecta", "Lepidoptera", "Nymphalidae", "Vanessa"),
    ReportItem("Ground beetle under log", "Carabus nemoralis", "Shiny ground beetle found under log.", "Mixed forest", "Arthropoda", "Insecta", "Coleoptera", "Carabidae", "Carabus"),
    ReportItem("Seven-spot ladybird", "Coccinella septempunctata", "Ladybird on leaf hunting aphids.", "Urban garden", "Arthropoda", "Insecta", "Coleoptera", "Coccinellidae", "Coccinella"),
    ReportItem("Honey bee on blossom", "Apis mellifera", "Honey bee collecting nectar.", "Orchard", "Arthropoda", "Insecta", "Hymenoptera", "Apidae", "Apis"),
    ReportItem("Bumblebee on clover", "Bombus terrestris", "Bumblebee visiting clover flowers.", "Meadow", "Arthropoda", "Insecta", "Hymenoptera", "Apidae", "Bombus"),

    # Molluscs
    ReportItem("Roman snail after rain", "Helix pomatia", "Large land snail moving across path.", "Central Europe", "Mollusca", "Gastropoda", "Stylommatophora", "Helicidae", "Helix"),
    ReportItem("Common octopus camouflage", "Octopus vulgaris", "Octopus camouflaging among rocks.", "Mediterranean Sea", "Mollusca", "Cephalopoda", "Octopoda", "Octopodidae", "Octopus"),

    # Marine mammals & others
    ReportItem("Common dolphin pod", "Delphinus delphis", "Small pod of common dolphins bow-riding.", "Bay of Biscay", "Chordata", "Mammalia", "Cetacea", "Delphinidae", "Delphinus"),
    ReportItem("Blue whale spout", "Balaenoptera musculus", "Distant blue whale with tall spout.", "Pacific Ocean", "Chordata", "Mammalia", "Cetacea", "Balaenopteridae", "Balaenoptera"),
    ReportItem("Nuthatch on tree trunk", "Sitta europaea", "Nuthatch climbing headfirst down trunk.", "Beech woodland", "Chordata", "Aves", "Passeriformes", "Sittidae", "Sitta"),
]


def login(session: requests.Session, email: str, password: str) -> bool:
    # get login page to establish session cookie
    session.get(f"{BASE_URL}/login")
    resp = session.post(
        f"{BASE_URL}/login",
        data={"email": email, "password": password},
        allow_redirects=False,
    )
    return resp.status_code in (302, 303)


def register(session: requests.Session, email: str, password: str, display_name: str) -> bool:
    session.get(f"{BASE_URL}/register")
    resp = session.post(
        f"{BASE_URL}/register",
        data={"email": email, "password": password, "display_name": display_name},
        allow_redirects=False,
    )
    # 303 on success, 400 with HTML on duplicate
    return resp.status_code in (302, 303)


def ensure_login(session: requests.Session, email: str, password: str) -> None:
    if login(session, email, password):
        return
    # try register then login
    display_name = email.split("@")[0]
    if register(session, email, password, display_name):
        if login(session, email, password):
            return
    # direct DB fallback: create or update user password, then login
    if ensure_user_in_db(email, password, display_name):
        if login(session, email, password):
            return
    raise RuntimeError("Unable to login or register the user.")


def ensure_user_in_db(email: str, password: str, display_name: str) -> bool:
    try:
        # import app.db & models dynamically
        CURRENT_DIR = Path(__file__).resolve().parent
        PROJECT_ROOT = CURRENT_DIR.parent
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from app.db import SessionLocal, engine
        from app.models import Base, User
        from app.security import hash_password

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.email == email.lower()).one_or_none()
            if u is None:
                u = User(email=email.lower(), display_name=display_name, password_hash=hash_password(password), is_admin=False)
                db.add(u)
            else:
                u.display_name = display_name
                u.password_hash = hash_password(password)
            db.commit()
            return True
        finally:
            db.close()
    except Exception as e:
        return False


def get_user_id(email: str) -> Optional[int]:
    try:
        CURRENT_DIR = Path(__file__).resolve().parent
        PROJECT_ROOT = CURRENT_DIR.parent
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from app.db import SessionLocal
        from app.models import User
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.email == email.lower()).one_or_none()
            return u.id if u else None
        finally:
            db.close()
    except Exception:
        return None


def species_exists_for_user(user_id: int, species_name: str) -> bool:
    try:
        CURRENT_DIR = Path(__file__).resolve().parent
        PROJECT_ROOT = CURRENT_DIR.parent
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        from app.db import SessionLocal
        from app.models import SpeciesReport
        db = SessionLocal()
        try:
            q = db.query(SpeciesReport).filter(
                SpeciesReport.reporter_id == user_id,
                SpeciesReport.species_name.ilike(species_name)
            )
            return db.query(q.exists()).scalar()
        finally:
            db.close()
    except Exception:
        return False


def submit_report(session: requests.Session, item: ReportItem) -> None:
    # Find image URL if missing
    img_url = item.photo_url or find_image_url(session, item.species_name)
    if not img_url:
        print(f"[skip] No image found for {item.species_name}")
        return
    fetched = fetch_image(session, img_url)
    if not fetched:
        print(f"[skip] Unable to download image for {item.species_name}")
        return
    fname, content, mime = fetched
    img_bytes = io.BytesIO(content)
    files = {"photo1": (fname, img_bytes, mime)}
    data = {
        "title": item.title,
        "species_name": item.species_name,
        "description": item.description,
        "location_text": item.location_text,
        "phylum": item.phylum,
        "class_name": item.class_name,
        "order_name": item.order_name,
        "family": item.family,
        "genus": item.genus,
    }
    resp = session.post(f"{BASE_URL}/reports", data=data, files=files, allow_redirects=False)
    if resp.status_code not in (302, 303):
        raise RuntimeError(f"Submit failed: {resp.status_code} {resp.text[:200]}")


def fetch_image(session: requests.Session, url: str) -> Optional[Tuple[str, bytes, str]]:
    headers = {"User-Agent": DEFAULT_UA, "Accept": "image/*,*/*;q=0.8", "Referer": "https://commons.wikimedia.org/"}
    try:
        r = session.get(url, timeout=30, headers=headers)
        r.raise_for_status()
        # guess mime from url
        if url.lower().endswith(".png"):
            return ("photo.png", r.content, "image/png")
        else:
            return ("photo.jpg", r.content, "image/jpeg")
    except Exception as e:
        return None


def find_image_url(session: requests.Session, title: str) -> Optional[str]:
    """Use Wikipedia summary API to fetch a thumbnail for the species page."""
    try:
        from urllib.parse import quote
        api = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
        r = session.get(api, timeout=20, headers={"User-Agent": DEFAULT_UA, "Accept": "application/json"})
        if r.status_code != 200:
            return None
        data = r.json()
        thumb = data.get("thumbnail") or {}
        src = thumb.get("source")
        return src
    except Exception:
        return None


def main():
    # 默认使用普通用户账号（可用 APP_EMAIL/APP_PASSWORD 覆盖）
    email = os.environ.get("APP_EMAIL", "liusizhe0312@sohu.com")
    password = os.environ.get("APP_PASSWORD", "liusizhe0312")
    with requests.Session() as s:
        s.headers.update({"User-Agent": DEFAULT_UA})
        ensure_login(s, email, password)
        user_id = get_user_id(email)
        seen: Set[str] = set()
        for r in REPORTS:
            key = r.species_name.strip().lower()
            if key in seen:
                print(f"[skip] duplicate species in batch: {r.species_name}")
                continue
            if user_id and species_exists_for_user(user_id, r.species_name):
                print(f"[skip] already exists for user: {r.species_name}")
                continue
            submit_report(s, r)
            seen.add(key)
    print(f"Submitted {len(REPORTS)} reports to {BASE_URL}")


if __name__ == "__main__":
    main()
