import io

from raceindycar.cache import Cache
from raceindycar.iris import session_details
from raceindycar.logging import LOGGER
from raceindycar.pdf_lapchart import position_map
from raceindycar.pdf_scrape import enrichment_map

CDN_BASE = "http://www.imscdn.com/"
SECTION_DOC_TYPE = "Section Results"
LAP_CHART_DOC_TYPE = "Lap Chart"
LAP_CHART_FILENAME = "lapchart.pdf"
SECTION_FILENAME = "section.pdf"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def lap_chart_positions(race_id, session_id):
    try:
        path = download_report_pdf(race_id, session_id, LAP_CHART_DOC_TYPE, LAP_CHART_FILENAME)
        if path is None:
            return {}, True
        positions = {
            (normalize_car(car), str(lap).strip()): position
            for (car, lap), position in position_map(path).items()
        }
        return positions, True
    except Exception as exc:
        LOGGER.warning("Lap chart failed for %s: %s", race_id, exc)
        return {}, False


def pdf_metrics(race_id, session_id):
    try:
        path = download_report_pdf(race_id, session_id, SECTION_DOC_TYPE, SECTION_FILENAME)
        if path is None:
            return {}, True
        metrics = {
            (normalize_car(car), str(lap).strip()): values
            for (car, lap), values in enrichment_map(path).items()
        }
        return metrics, True
    except Exception as exc:
        LOGGER.warning("PDF metrics failed for %s: %s", race_id, exc)
        return {}, False


def discard_report_pdfs(race_id, session_id):
    for filename in (LAP_CHART_FILENAME, SECTION_FILENAME):
        Cache.path(str(race_id), str(session_id), filename).unlink(missing_ok=True)


def download_report_pdf(race_id, session_id, doc_type, filename):
    dest = Cache.path(str(race_id), str(session_id), filename)
    if Cache.should_read(dest):
        return dest
    if not session_id:
        return None
    url = report_url(session_details(session_id), doc_type)
    if not url:
        return None
    data = download_bytes(url)
    if Cache.should_write():
        Cache.write_bytes(dest, data)
        return dest
    return io.BytesIO(data)


def report_url(details, doc_type):
    for report in details.get("SessionReports") or []:
        if report.get("DocumentType") == doc_type and report.get("Url"):
            return CDN_BASE + report["Url"]
    return None


def download_bytes(url):
    response = Cache.requests_get(url, headers=HEADERS, timeout=120)
    return response.content


def normalize_car(value):
    text = str(value or "").strip()
    return str(int(text)) if text.isdigit() else text
