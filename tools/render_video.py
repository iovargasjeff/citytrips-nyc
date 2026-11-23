"""Render the Spanish CityTrips explainer from the published aggregate data.

Requirements: Windows, Pillow, ffmpeg/ffprobe, and a Spanish System.Speech voice.
Run from the project root: py tools/render_video.py
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import textwrap
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORK_DIR = ROOT / "deliverables" / ".video_work"
OUTPUT_DIR = ROOT / "deliverables"
PUBLIC_BASE = "https://iovargasjeff.github.io/citytrips-nyc/data"
VIDEO_SCRIPT = ROOT / "docs" / "guion-video-es.md"
VOICE_SCRIPT = ROOT / "tools" / "video_voice.ps1"
WIDTH, HEIGHT = 1920, 1080

BG_TOP = (14, 23, 33)
BG_BOTTOM = (9, 16, 24)
PANEL = (24, 35, 49)
PANEL_ALT = (29, 43, 58)
TEXT = (244, 242, 237)
MUTED = (153, 168, 181)
MINT = (136, 224, 208)
YELLOW = (247, 196, 84)
RED = (243, 119, 106)
BLUE = (102, 169, 235)
GRID = (29, 43, 57)


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    filename = "seguisb.ttf" if bold else "segoeui.ttf"
    path = Path("C:/Windows/Fonts") / filename
    if not path.exists():
        path = Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf")
    return ImageFont.truetype(str(path), size)


def fetch_json(name: str) -> Any:
    cache_path = WORK_DIR / "source" / name
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        f"{PUBLIC_BASE}/{name}", headers={"User-Agent": "CityTrips-NYC-video/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    cache_path.write_bytes(data)
    return json.loads(data)


def load_storyboard() -> list[dict[str, str]]:
    rows = []
    for line in VIDEO_SCRIPT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("| Tiempo") or line.startswith("| ---"):
            continue
        columns = [part.strip() for part in line.strip("|").split("|")]
        if len(columns) == 3:
            rows.append({"time": columns[0], "visual": columns[1], "spoken": columns[2]})
    if len(rows) != 9:
        raise ValueError(f"Expected 9 scenes in {VIDEO_SCRIPT}, found {len(rows)}")
    return rows


def background(
    scene_number: int, title: str, eyebrow: str
) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()
    for y in range(HEIGHT):
        ratio = y / max(1, HEIGHT - 1)
        color = tuple(
            int(top * (1 - ratio) + bottom * ratio)
            for top, bottom in zip(BG_TOP, BG_BOTTOM, strict=True)
        )
        for x in range(WIDTH):
            pixels[x, y] = color
    draw = ImageDraw.Draw(image)
    for x in range(60, WIDTH, 72):
        draw.line((x, 0, x, HEIGHT), fill=GRID, width=1)
    for y in range(40, HEIGHT, 72):
        draw.line((0, y, WIDTH, y), fill=GRID, width=1)
    draw.rounded_rectangle((54, 38, 1866, 1042), radius=28, outline=(48, 65, 81), width=2)
    draw.text((96, 67), "CITYTRIPS NYC", font=get_font(22, True), fill=MINT)
    draw.text((365, 72), eyebrow.upper(), font=get_font(16, True), fill=MUTED)
    draw.text((96, 136), title, font=get_font(48, True), fill=TEXT)
    draw.rounded_rectangle((96, 1000, 1824, 1004), radius=3, fill=(52, 67, 82))
    draw.rounded_rectangle((96, 1000, 96 + int(1728 * scene_number / 9), 1004), radius=3, fill=MINT)
    draw.text(
        (96, 1018),
        "NYC TAXI & LIMOUSINE COMMISSION · DATOS AGREGADOS",
        font=get_font(14),
        fill=MUTED,
    )
    draw.text((1670, 1015), f"{scene_number:02d} / 09", font=get_font(16, True), fill=MUTED)
    return image, draw


def rounded_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill=PANEL) -> None:
    draw.rounded_rectangle(box, radius=18, fill=fill, outline=(55, 72, 90), width=2)


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    width: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def save_scene(image: Image.Image, index: int) -> Path:
    path = WORK_DIR / f"scene-{index:02d}.png"
    image.save(path, optimize=True)
    return path


def draw_hero(scene: dict[str, str], i: int, manifest: dict[str, Any]) -> Path:
    image, draw = background(i, "Una ciudad entera, un pipeline reproducible", "El resultado")
    rows = manifest["source_total_rows"]
    months = manifest["source_month_count"]
    latest = manifest["latest_month"]
    draw.text((110, 250), f"{rows / 1_000_000:.2f}M", font=get_font(144, True), fill=TEXT)
    draw.text((120, 433), "filas de viajes verificadas", font=get_font(32), fill=MINT)
    draw.text(
        (120, 505), f"{months} meses · {latest} · NYC Yellow Taxi", font=get_font(26), fill=MUTED
    )
    for idx, (value, label, color) in enumerate(
        [
            (f"{months}", "archivos Parquet", MINT),
            ("263", "zonas TLC", YELLOW),
            ("1", "sitio público", BLUE),
        ]
    ):
        x = 116 + idx * 385
        rounded_card(draw, (x, 665, x + 350, 825))
        draw.text((x + 28, 685), value, font=get_font(48, True), fill=color)
        draw.text((x + 30, 755), label, font=get_font(21), fill=MUTED)
    rounded_card(draw, (1300, 255, 1760, 550), PANEL_ALT)
    draw.text((1340, 292), "123.47M", font=get_font(57, True), fill=YELLOW)
    draw.text((1342, 371), "filas de origen", font=get_font(22), fill=MUTED)
    draw.line((1342, 423, 1700, 423), fill=(67, 87, 105), width=3)
    draw.text(
        (1342, 450), "datos abiertos · pipeline batch · web estática", font=get_font(18), fill=TEXT
    )
    return save_scene(image, i)


def draw_architecture(scene: dict[str, str], i: int) -> Path:
    image, draw = background(i, "Del registro mensual a una demo compartible", "Arquitectura")
    nodes = [
        ("TLC", "Parquet +\nzonas", YELLOW),
        ("Python", "descarga\n+ SHA-256", MINT),
        ("dbt Core", "staging +\npruebas", BLUE),
        ("DuckDB", "marts\nanalíticos", YELLOW),
        ("JSON", "agregados\n+ GeoJSON", MINT),
        ("React", "dashboard\npúblico", BLUE),
    ]
    start_x, gap, card_w = 102, 28, 260
    for idx, (name, detail, color) in enumerate(nodes):
        x = start_x + idx * (card_w + gap)
        rounded_card(draw, (x, 330, x + card_w, 520))
        draw.ellipse((x + 22, 352, x + 42, 372), fill=color)
        draw.text((x + 58, 342), name, font=get_font(29, True), fill=TEXT)
        for line_idx, line in enumerate(detail.split("\n")):
            draw.text((x + 24, 417 + line_idx * 35), line, font=get_font(22), fill=MUTED)
        if idx < len(nodes) - 1:
            ax = x + card_w + 3
            draw.line((ax, 424, ax + gap - 8, 424), fill=MINT, width=4)
            draw.polygon([(ax + gap - 8, 414), (ax + gap, 424), (ax + gap - 8, 434)], fill=MINT)
    rounded_card(draw, (355, 650, 1565, 815), PANEL_ALT)
    draw.text((405, 681), "GitHub Actions", font=get_font(32, True), fill=TEXT)
    draw.text(
        (405, 736),
        "orquesta tests, refresh mensual y publicación en GitHub Pages",
        font=get_font(24),
        fill=MUTED,
    )
    draw.line((480, 650, 480, 535), fill=(81, 113, 132), width=3)
    draw.line((1440, 650, 1440, 535), fill=(81, 113, 132), width=3)
    return save_scene(image, i)


def draw_ingest(scene: dict[str, str], i: int, manifest: dict[str, Any]) -> Path:
    image, draw = background(i, "Cada archivo trae identidad y evidencia", "Ingesta")
    months = manifest["published_months"]
    card_w, card_h, gap = 126, 74, 12
    for idx, month in enumerate(months):
        col = idx % 11
        row = idx // 11
        x = 100 + col * (card_w + gap)
        y = 253 + row * (card_h + 12)
        rounded_card(draw, (x, y, x + card_w, y + card_h), PANEL_ALT)
        draw.text(
            (x + 18, y + 23),
            month,
            font=get_font(20, True),
            fill=MINT if month == manifest["latest_month"] else TEXT,
        )
    rounded_card(draw, (100, 572, 920, 825))
    draw.text((135, 604), "33 / 33", font=get_font(62, True), fill=MINT)
    draw.text((139, 684), "archivos detectados y leídos", font=get_font(24), fill=TEXT)
    draw.text((139, 750), "manifiesto · SHA-256 · caché verificada", font=get_font(20), fill=MUTED)
    rounded_card(draw, (1000, 572, 1815, 825), PANEL_ALT)
    draw.text((1040, 604), "REUSE / DOWNLOAD", font=get_font(20, True), fill=YELLOW)
    draw_wrapped(
        draw,
        "Antes de reutilizar un Parquet, el workflow compara los metadatos HTTP y "
        "vuelve a validar su checksum.",
        (1040, 664),
        get_font(24),
        TEXT,
        715,
        12,
    )
    return save_scene(image, i)


def draw_schema(scene: dict[str, str], i: int) -> Path:
    image, draw = background(i, "La ausencia no es un importe cero", "Evolución de esquema")
    cards = [
        (110, "ARCHIVO ANTIGUO", "cbd_congestion_fee", "NULL", "el campo todavía no existe", BLUE),
        (705, "ARCHIVO NUEVO", "cbd_congestion_fee", "$0.00", "cero informado por el origen", MINT),
        (1300, "ARCHIVO NUEVO", "cbd_congestion_fee", "$0.50", "importe informado", YELLOW),
    ]
    for x, header, field, value, note, accent in cards:
        rounded_card(draw, (x, 300, x + 500, 730))
        draw.text((x + 34, 338), header, font=get_font(18, True), fill=accent)
        draw.text((x + 34, 402), field, font=get_font(22, True), fill=TEXT)
        draw.text((x + 34, 493), value, font=get_font(66, True), fill=accent)
        draw.line((x + 34, 595, x + 462, 595), fill=(65, 80, 97), width=2)
        draw_wrapped(draw, note, (x + 34, 631), get_font(20), MUTED, 410, 9)
    draw.text((722, 795), "NULL ≠ 0", font=get_font(36, True), fill=TEXT)
    return save_scene(image, i)


def draw_quality(
    scene: dict[str, str], i: int, manifest: dict[str, Any], quality: list[dict[str, Any]]
) -> Path:
    image, draw = background(i, "Las cifras se concilian antes de publicar", "Modelado & calidad")
    source = sum(row["source_rows"] for row in quality)
    accepted = sum(row["accepted_rows"] for row in quality)
    rejected = sum(row["rejected_rows"] for row in quality)
    draw.text((120, 285), f"{source / 1_000_000:.2f}M", font=get_font(80, True), fill=TEXT)
    draw.text((126, 384), "filas fuente", font=get_font(25), fill=MUTED)
    draw.text((126, 454), "=", font=get_font(38, True), fill=MUTED)
    draw.text((126, 526), f"{accepted / 1_000_000:.2f}M", font=get_font(54, True), fill=MINT)
    draw.text((126, 596), "aceptadas", font=get_font(22), fill=MUTED)
    draw.text((385, 526), "+", font=get_font(38, True), fill=MUTED)
    draw.text((460, 526), f"{rejected / 1_000_000:.2f}M", font=get_font(54, True), fill=RED)
    draw.text((460, 596), "rechazadas", font=get_font(22), fill=MUTED)
    left, top, width = 120, 700, 790
    draw.rounded_rectangle((left, top, left + width, top + 30), radius=14, fill=(47, 63, 77))
    accepted_width = int(width * accepted / source)
    draw.rounded_rectangle((left, top, left + accepted_width, top + 30), radius=14, fill=MINT)
    draw.rounded_rectangle(
        (left + accepted_width - 10, top, left + width, top + 30), radius=14, fill=RED
    )
    rounded_card(draw, (1010, 290, 1790, 785), PANEL_ALT)
    draw.text((1058, 338), "PRUEBAS EN EL REPO", font=get_font(19, True), fill=YELLOW)
    checks = [("10", "pruebas Python"), ("26", "checks de dbt"), ("7", "pruebas frontend")]
    for idx, (number, label) in enumerate(checks):
        y = 420 + idx * 100
        draw.text((1060, y), number, font=get_font(42, True), fill=MINT)
        draw.text((1180, y + 6), label, font=get_font(25), fill=TEXT)
    draw.text((1060, 730), "fuente = aceptadas + rechazadas", font=get_font(18), fill=MUTED)
    return save_scene(image, i)


def draw_dashboard(
    scene: dict[str, str], i: int, monthly: list[dict[str, Any]], hourly: list[dict[str, Any]]
) -> Path:
    image, draw = background(i, "Tendencia y ritmo de la ciudad", "Dashboard")
    rounded_card(draw, (105, 250, 1000, 825))
    draw.text(
        (145, 284), "PROMEDIO DE VIAJES POR DÍA CALENDARIO", font=get_font(17, True), fill=MUTED
    )
    chart_box = (170, 365, 940, 720)
    for idx in range(5):
        y = chart_box[1] + idx * (chart_box[3] - chart_box[1]) / 4
        draw.line((chart_box[0], y, chart_box[2], y), fill=GRID, width=2)
    values = [row["trips_per_calendar_day"] for row in monthly]
    low, high = min(values), max(values)
    points = []
    for idx, value in enumerate(values):
        x = chart_box[0] + idx * (chart_box[2] - chart_box[0]) / max(1, len(values) - 1)
        y = chart_box[3] - (value - low) / max(1, high - low) * (chart_box[3] - chart_box[1])
        points.append((int(x), int(y)))
    draw.line(points, fill=MINT, width=5, joint="curve")
    for idx, point in enumerate(points):
        if idx % 4 == 0 or idx == len(points) - 1:
            draw.ellipse((point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5), fill=YELLOW)
            draw.text(
                (point[0] - 27, chart_box[3] + 18),
                monthly[idx]["month"],
                font=get_font(13),
                fill=MUTED,
            )
    rounded_card(draw, (1040, 250, 1815, 825), PANEL_ALT)
    draw.text((1080, 284), "VIAJES POR DÍA Y HORA", font=get_font(17, True), fill=MUTED)
    totals: dict[tuple[int, int], int] = defaultdict(int)
    for row in hourly:
        totals[(int(row["weekday"]), int(row["hour"]))] += int(row["trip_count"])
    vmax = max(totals.values())
    x0, y0, cell_w, cell_h, space = 1100, 385, 22, 36, 4
    day_short = ["D", "L", "M", "X", "J", "V", "S"]
    for day in range(7):
        draw.text(
            (1060, y0 + day * (cell_h + space) + 7),
            day_short[day],
            font=get_font(15, True),
            fill=MUTED,
        )
        for hour in range(24):
            val = totals[(day, hour)]
            intensity = math.sqrt(val / vmax) if vmax else 0
            color = (
                int(33 + intensity * 103),
                int(49 + intensity * 164),
                int(67 + intensity * 145),
            )
            x = x0 + hour * (cell_w + 3)
            y = y0 + day * (cell_h + space)
            draw.rounded_rectangle((x, y, x + cell_w, y + cell_h), radius=5, fill=color)
    draw.text((x0, 715), "00:00", font=get_font(14), fill=MUTED)
    draw.text((x0 + 12 * 25, 715), "12:00", font=get_font(14), fill=MUTED)
    draw.text((x0 + 22 * 25, 715), "23:00", font=get_font(14), fill=MUTED)
    return save_scene(image, i)


def feature_rings(feature: dict[str, Any]) -> list[list[list[float]]]:
    geometry = feature.get("geometry") or {}
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "Polygon":
        return coordinates[:1]
    if kind == "MultiPolygon":
        return [polygon[0] for polygon in coordinates if polygon]
    return []


def draw_zones(
    scene: dict[str, str], i: int, zones: dict[str, Any], zone_month: list[dict[str, Any]]
) -> Path:
    image, draw = background(i, "263 zonas TLC; un mapa con trazabilidad", "Geografía")
    totals: dict[int, int] = defaultdict(int)
    for row in zone_month:
        totals[int(row["location_id"])] += int(row["trip_count"])
    all_points = [
        pt for feature in zones["features"] for ring in feature_rings(feature) for pt in ring
    ]
    longitudes = [point[0] for point in all_points]
    latitudes = [point[1] for point in all_points]
    mid_lat = sum(latitudes) / max(1, len(latitudes))
    cos_lat = math.cos(math.radians(mid_lat))
    min_x, max_x = min(longitudes) * cos_lat, max(longitudes) * cos_lat
    min_y, max_y = min(latitudes), max(latitudes)
    bounds = (140, 250, 1200, 850)
    scale = min(
        (bounds[2] - bounds[0]) / (max_x - min_x), (bounds[3] - bounds[1]) / (max_y - min_y)
    )
    x_offset = bounds[0] + ((bounds[2] - bounds[0]) - (max_x - min_x) * scale) / 2
    y_offset = bounds[1] + ((bounds[3] - bounds[1]) - (max_y - min_y) * scale) / 2
    positive = sorted(value for value in totals.values() if value > 0)
    cap = positive[int(0.96 * (len(positive) - 1))] if positive else 1
    for feature in zones["features"]:
        location_id = int(feature["properties"].get("LocationID", 0))
        value = totals.get(location_id, 0)
        intensity = min(1.0, math.log1p(value) / math.log1p(cap)) if cap else 0
        color = (int(32 + intensity * 75), int(49 + intensity * 174), int(65 + intensity * 150))
        for ring in feature_rings(feature):
            polygon = []
            for longitude, latitude in ring:
                x = x_offset + (longitude * cos_lat - min_x) * scale
                y = y_offset + (max_y - latitude) * scale
                polygon.append((int(x), int(y)))
            if len(polygon) >= 3:
                draw.polygon(polygon, fill=color, outline=(105, 131, 145))
    top_locations: dict[int, dict[str, Any]] = {}
    for row in zone_month:
        location_id = int(row["location_id"])
        top_locations.setdefault(
            location_id, {"zone": row["zone_name"], "borough": row["borough"], "trips": 0}
        )
        top_locations[location_id]["trips"] += int(row["trip_count"])
    top = sorted(top_locations.values(), key=lambda row: row["trips"], reverse=True)[:5]
    rounded_card(draw, (1260, 260, 1800, 840), PANEL_ALT)
    draw.text((1304, 300), "MÁS ACTIVAS", font=get_font(19, True), fill=YELLOW)
    for idx, row in enumerate(top):
        y = 365 + idx * 92
        draw.text((1304, y), f"{idx + 1:02d}  {row['zone']}", font=get_font(20, True), fill=TEXT)
        draw.text(
            (1344, y + 31),
            f"{row['borough']} · {row['trips'] / 1_000_000:.2f} M",
            font=get_font(17),
            fill=MUTED,
        )
    draw.text(
        (1304, 812), f"{len(zones['features'])} límites oficiales", font=get_font(17), fill=MINT
    )
    return save_scene(image, i)


def draw_automation(scene: dict[str, str], i: int) -> Path:
    image, draw = background(i, "Una ejecución verde se convierte en publicación", "Automatización")
    steps = ["ingest", "dbt build", "quality tests", "npm test", "vite build", "Pages"]
    x0, card_w, gap = 108, 260, 27
    for idx, step in enumerate(steps):
        x = x0 + idx * (card_w + gap)
        rounded_card(draw, (x, 375, x + card_w, 535), PANEL_ALT)
        draw.ellipse((x + 22, 398, x + 56, 432), fill=MINT)
        draw.line((x + 31, 415, x + 39, 423), fill=BG_TOP, width=3)
        draw.line((x + 39, 423, x + 50, 406), fill=BG_TOP, width=3)
        draw.text((x + 22, 456), step, font=get_font(25, True), fill=TEXT)
        if idx < len(steps) - 1:
            draw.line((x + card_w + 3, 453, x + card_w + gap - 8, 453), fill=MINT, width=4)
            draw.polygon(
                [(x + card_w + gap - 8, 444), (x + card_w + gap, 453), (x + card_w + gap - 8, 462)],
                fill=MINT,
            )
    rounded_card(draw, (285, 660, 1635, 825))
    draw.text((333, 690), "mensual · día 10", font=get_font(29, True), fill=YELLOW)
    draw.text(
        (333, 747),
        "manual bajo demanda · la última versión válida sigue pública",
        font=get_font(23),
        fill=MUTED,
    )
    return save_scene(image, i)


def draw_closing(scene: dict[str, str], i: int, manifest: dict[str, Any]) -> Path:
    image, draw = background(
        i, "Datos abiertos. Código abierto. Resultado verificable.", "Explora CityTrips NYC"
    )
    draw.text(
        (122, 275), f"{manifest['source_month_count']} meses", font=get_font(51, True), fill=MINT
    )
    draw.text(
        (122, 355),
        f"{manifest['source_total_rows'] / 1_000_000:.2f} millones de filas",
        font=get_font(31),
        fill=TEXT,
    )
    rounded_card(draw, (120, 530, 1795, 680), PANEL_ALT)
    draw.text((166, 567), "DEMO", font=get_font(20, True), fill=YELLOW)
    draw.text(
        (350, 557), "iovargasjeff.github.io/citytrips-nyc", font=get_font(32, True), fill=TEXT
    )
    rounded_card(draw, (120, 715, 1795, 865))
    draw.text((166, 752), "CÓDIGO", font=get_font(20, True), fill=MINT)
    draw.text(
        (350, 742), "github.com/iovargasjeff/citytrips-nyc", font=get_font(32, True), fill=TEXT
    )
    draw.text(
        (125, 916),
        f"Snapshot: {manifest['latest_month']} · Fuente: NYC TLC",
        font=get_font(18),
        fill=MUTED,
    )
    return save_scene(image, i)


def render_images(scenes: list[dict[str, str]]) -> list[Path]:
    manifest = fetch_json("manifest.json")
    monthly = fetch_json("monthly.json")
    hourly = fetch_json("monthly_hour.json")
    zone_month = fetch_json("zone_month.json")
    quality = fetch_json("quality.json")
    zones = fetch_json("taxi_zones.geojson")
    renderers = [
        lambda row, idx: draw_hero(row, idx, manifest),
        lambda row, idx: draw_architecture(row, idx),
        lambda row, idx: draw_ingest(row, idx, manifest),
        lambda row, idx: draw_schema(row, idx),
        lambda row, idx: draw_quality(row, idx, manifest, quality),
        lambda row, idx: draw_dashboard(row, idx, monthly, hourly),
        lambda row, idx: draw_zones(row, idx, zones, zone_month),
        lambda row, idx: draw_automation(row, idx),
        lambda row, idx: draw_closing(row, idx, manifest),
    ]
    return [render(scenes[idx], idx + 1) for idx, render in enumerate(renderers)]


def run_voice(lines: list[str]) -> None:
    lines_path = WORK_DIR / "narration.json"
    lines_path.write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    voice_output = WORK_DIR / "voice"
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(VOICE_SCRIPT),
        "-LinesFile",
        str(lines_path),
        "-OutputDirectory",
        str(voice_output),
    ]
    subprocess.run(command, check=True, cwd=ROOT)


def media_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def ass_timecode(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds_int, milliseconds = divmod(remainder, 1000)
    centiseconds = milliseconds // 10
    return f"{hours}:{minutes:02}:{seconds_int:02}.{centiseconds:02}"


def caption_sentences(text: str) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return [
        "\n".join(textwrap.wrap(sentence, width=72, break_long_words=False, break_on_hyphens=False))
        for sentence in sentences
    ]


def write_ass(scenes: list[dict[str, str]], audio_lengths: list[float]) -> None:
    style_fields = [
        "Name",
        "Fontname",
        "Fontsize",
        "PrimaryColour",
        "SecondaryColour",
        "OutlineColour",
        "BackColour",
        "Bold",
        "Italic",
        "BorderStyle",
        "Outline",
        "Shadow",
        "Alignment",
        "MarginL",
        "MarginR",
        "MarginV",
        "Encoding",
    ]
    event_fields = [
        "Layer",
        "Start",
        "End",
        "Style",
        "Name",
        "MarginL",
        "MarginR",
        "MarginV",
        "Effect",
        "Text",
    ]
    style_values = [
        "Default",
        "Arial",
        "34",
        "&H00F4F2ED",
        "&H000000FF",
        "&HAA0B1218",
        "&HAA0B1218",
        "0",
        "0",
        "1",
        "2",
        "0",
        "2",
        "72",
        "72",
        "102",
        "1",
    ]
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1920\n"
        "PlayResY: 1080\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n\n"
        "[V4+ Styles]\n"
        f"Format: {', '.join(style_fields)}\n"
        f"Style: {','.join(style_values)}\n\n"
        "[Events]\n"
        f"Format: {', '.join(event_fields)}\n"
    )
    events = []
    cursor = 0.0
    for scene, audio_length in zip(scenes, audio_lengths, strict=True):
        captions = caption_sentences(scene["spoken"])
        sentence_words = [max(1, len(line.split())) for line in captions]
        total_words = sum(sentence_words)
        consumed = 0
        for caption, words in zip(captions, sentence_words, strict=True):
            start = cursor + audio_length * consumed / total_words
            consumed += words
            end = cursor + audio_length * consumed / total_words
            ass_caption = caption.replace("\n", r"\N").replace("{", r"\{").replace("}", r"\}")
            events.append(
                "Dialogue: 0,"
                f"{ass_timecode(start)},{ass_timecode(end)},Default,,0,0,0,,{ass_caption}"
            )
        cursor += audio_length + 1.8
    (WORK_DIR / "captions.ass").write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def build_video(scenes: list[dict[str, str]], images: list[Path]) -> tuple[Path, float]:
    voice_dir = WORK_DIR / "voice"
    voice_files = [voice_dir / f"narration-{idx:02}.wav" for idx in range(1, len(scenes) + 1)]
    audio_lengths = [media_duration(path) for path in voice_files]
    if sum(audio_lengths) > 299:
        raise ValueError(
            f"Narration alone is {sum(audio_lengths):.1f}s; reduce it below five minutes."
        )
    write_ass(scenes, audio_lengths)

    clips = []
    for idx, (image_path, audio_path, audio_length) in enumerate(
        zip(images, voice_files, audio_lengths, strict=True), 1
    ):
        clip_path = WORK_DIR / f"clip-{idx:02}.mp4"
        duration = audio_length + 1.8
        fade_out_start = max(0, audio_length + 0.7)
        video_filter = (
            "zoompan=z='min(zoom+0.00015,1.035)':d=1:s=1920x1080:fps=30,"
            "format=yuv420p,fade=t=in:st=0:d=0.25"
        )
        audio_filter = (
            f"aresample=48000,apad=pad_dur=2.0,afade=t=out:st={fade_out_start:.3f}:d=0.45"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-framerate",
                "30",
                "-i",
                str(image_path),
                "-i",
                str(audio_path),
                "-t",
                f"{duration:.3f}",
                "-vf",
                video_filter,
                "-af",
                audio_filter,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(clip_path),
            ],
            check=True,
            cwd=ROOT,
        )
        clips.append(clip_path)
        print(f"Rendered scene {idx}/{len(scenes)} · {duration:.1f}s")

    concat_path = WORK_DIR / "clips.txt"
    concat_path.write_text(
        "\n".join(f"file '{path.as_posix()}'" for path in clips), encoding="utf-8"
    )
    raw_path = WORK_DIR / "citytrips-raw.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(raw_path),
        ],
        check=True,
        cwd=ROOT,
    )

    output = OUTPUT_DIR / "CityTrips-NYC.mp4"
    subtitles_filter = "subtitles=deliverables/.video_work/captions.ass"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(raw_path),
            "-vf",
            subtitles_filter,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
        cwd=ROOT,
    )
    return output, media_duration(output)


def main() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scenes = load_storyboard()
    lines = [scene["spoken"] for scene in scenes]
    images = render_images(scenes)
    Image.open(images[0]).save(OUTPUT_DIR / "CityTrips-NYC-cover.png", optimize=True)
    run_voice(lines)
    video_path, duration = build_video(scenes, images)
    print(f"Video: {video_path}")
    print(f"Duration: {duration:.2f}s ({duration / 60:.2f} min)")
    print(f"Size: {video_path.stat().st_size / 1_000_000:.1f} MB")


if __name__ == "__main__":
    main()
