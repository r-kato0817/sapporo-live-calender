#!/usr/bin/env python3
"""PRECIOUS HALL (Sapporo) schedule -> iCalendar (.ics) generator.

Scrapes the official "Pick Up" schedule page and each event's detail page,
then writes an ICS file that can be subscribed to in Google Calendar.

Source: http://www.precioushall.com/schedule/
"""

import argparse
import datetime
import html
import json
import re
import sys
import time
import urllib.request

SCHEDULE_URL = "http://www.precioushall.com/schedule/"
USER_AGENT = "Mozilla/5.0 (compatible; precioushall-cal/1.0)"
TIMEOUT = 30
DEFAULT_DURATION = datetime.timedelta(hours=6)

CALNAME = "PRECIOUS HALL Schedule (Sapporo)"
CALTZ = "Asia/Tokyo"
LOCATION = "PRECIOUS HALL (Parade B2F, 札幌市中央区南2条西3丁目)"

VTIMEZONE = "\r\n".join([
    "BEGIN:VTIMEZONE",
    "TZID:Asia/Tokyo",
    "BEGIN:STANDARD",
    "DTSTART:19700101T000000",
    "TZOFFSETFROM:+0900",
    "TZOFFSETTO:+0900",
    "TZNAME:JST",
    "END:STANDARD",
    "END:VTIMEZONE",
])


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def decode(data: bytes) -> str:
    for enc in ("utf-8", "shift_jis"):
        try:
            text = data.decode(enc)
            if "\ufffd" not in text:
                return text
        except UnicodeDecodeError:
            continue
    return data.decode("shift_jis", errors="replace")


def fetch(url: str) -> str:
    return decode(fetch_bytes(url))


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return html.unescape(s)


def parse_schedule(html_text: str) -> list:
    events = []
    for m in re.finditer(
        r'<div class="sp_flyer" id="(?P<dateid>\d{8})">.*?'
        r'<div class="textblock">(?P<body>.*?)</div>\s*</div>',
        html_text,
        re.S,
    ):
        body = m.group("body")
        dateid = m.group("dateid")
        year, month, day = int(dateid[0:4]), int(dateid[4:6]), int(dateid[6:8])

        tm = re.search(r'<h3><a href="([^"]+)">(.*?)</a></h3>', body, re.S)
        if not tm:
            continue
        path, title = tm.group(1), strip_tags(tm.group(2))

        sub = re.search(r"<h4>(.*?)</h4>", body, re.S)
        subtitle = strip_tags(sub.group(1)) if sub else None

        details = []
        for dt, dd in re.findall(r"<dl[^>]*>\s*<dt>(.*?)</dt>(.*?)</dl>", body, re.S):
            label = strip_tags(dt)
            if label.endswith(":"):
                label = label[:-1]
            details.append({"label": label, "value": strip_tags(dd)})

        events.append({
            "dateid": dateid,
            "year": year,
            "month": month,
            "day": day,
            "title": title,
            "subtitle": subtitle,
            "details": details,
            "path": path,
            "detail_url": SCHEDULE_URL + path,
        })
    return events


def parse_detail(html_text: str):
    adm = None
    start_hm = None
    m = re.search(r'<p class="fee">(.*?)</p>', html_text, re.S)
    if m:
        adm = strip_tags(m.group(1))
        adm = re.split(r"PRECIOUS HALL", adm, flags=re.I)[0].strip()
        adm = re.sub(r"^\s*ADM\s*:", "", adm).strip()
        tm = re.search(r"(\d{1,2}):(\d{2})", adm)
        if tm:
            start_hm = (int(tm.group(1)), int(tm.group(2)))
    return adm, start_hm


def slugify(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()
    return s or "event"


def esc(value: str) -> str:
    return (value.replace("\\", "\\\\")
                 .replace(";", "\\;")
                 .replace(",", "\\,")
                 .replace("\n", "\\n"))


def fold(line: str) -> str:
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts = []
    i = 0
    while i < len(raw):
        end = min(i + 75, len(raw))
        if end < len(raw) and (raw[end] & 0xC0) == 0x80:
            while end > i and (raw[end] & 0xC0) == 0x80:
                end -= 1
        if end <= i:
            end = i + 1
        parts.append(raw[i:end].decode("utf-8"))
        i = end
    return "\r\n ".join(parts)


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_description(ev: dict, adm, start_hm) -> str:
    sections = []
    if ev["subtitle"]:
        sections.append("Subtitle: " + ev["subtitle"])
    if ev["details"]:
        sections.append("LINEUP:\n" + "\n".join(
            "{}: {}".format(d["label"], d["value"]) for d in ev["details"]))
    if adm:
        sections.append("ADM: " + adm)
    if start_hm:
        sections.append(
            "START: {:02d}:{:02d} (end time not published, ~6h assumed)"
            .format(*start_hm))
    sections.append("Details: " + ev["detail_url"])
    return "\n\n".join(sections)


def build_event(ev: dict, adm, start_hm) -> str:
    uid = "precioushall-{dateid}-{slug}@precioushall.com".format(
        dateid=ev["dateid"], slug=slugify(ev["title"]))
    d = datetime.date(ev["year"], ev["month"], ev["day"])
    summary = "{} @ PRECIOUS HALL".format(ev["title"])

    lines = ["BEGIN:VEVENT"]
    lines.append("UID:" + uid)
    lines.append("DTSTAMP:" + now_utc())
    lines.append("SUMMARY:" + esc(summary))
    lines.append("LOCATION:" + esc(LOCATION))
    if start_hm:
        start_dt = datetime.datetime(
            ev["year"], ev["month"], ev["day"], start_hm[0], start_hm[1])
        end_dt = start_dt + DEFAULT_DURATION
        lines.append("DTSTART;TZID=Asia/Tokyo:" + start_dt.strftime("%Y%m%dT%H%M%S"))
        lines.append("DTEND;TZID=Asia/Tokyo:" + end_dt.strftime("%Y%m%dT%H%M%S"))
    else:
        lines.append("DTSTART;VALUE=DATE:" + d.strftime("%Y%m%d"))
        lines.append("DTEND;VALUE=DATE:" + (d + datetime.timedelta(days=1)).strftime("%Y%m%d"))
    lines.append("DESCRIPTION:" + esc(build_description(ev, adm, start_hm)))
    lines.append("URL:" + ev["detail_url"])
    lines.append("END:VEVENT")
    return fold("\r\n".join(lines))


def build_calendar(events: list) -> str:
    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//precioushall-calendar//precioushall.com//JA",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + CALNAME,
        "X-WR-CALDESC:PRECIOUS HALL (Sapporo) latest live schedule",
        "X-WR-TIMEZONE:" + CALTZ,
        VTIMEZONE,
    ]
    body = [build_event(ev, ev["adm"], ev["start_hm"]) for ev in events]
    parts = header + body + ["END:VCALENDAR", ""]
    return "\r\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="precioushall.ics")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="delay in seconds between detail-page requests")
    args = parser.parse_args()

    try:
        print("Fetching schedule page: " + SCHEDULE_URL)
        events = parse_schedule(fetch(SCHEDULE_URL))
    except Exception as exc:
        print("ERROR: failed to fetch schedule page: {}".format(exc), file=sys.stderr)
        return 1

    if not events:
        print("ERROR: no events parsed from schedule page", file=sys.stderr)
        return 1

    seen = set()
    for ev in events:
        if ev["dateid"] in seen:
            continue
        seen.add(ev["dateid"])
        try:
            print("Fetching detail: {}".format(ev["detail_url"]))
            ev["adm"], ev["start_hm"] = parse_detail(fetch(ev["detail_url"]))
            time.sleep(args.delay)
        except Exception as exc:
            print("WARN: failed to fetch detail page {}: {}".format(ev["detail_url"], exc),
                  file=sys.stderr)
            ev["adm"], ev["start_hm"] = None, None

    events = [ev for ev in events if ev["dateid"] in seen]

    cal = build_calendar(events)
    with open(args.output, "w", encoding="utf-8", newline="") as fh:
        fh.write(cal)

    summary = {
        "last_run": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds"),
        "source_url": SCHEDULE_URL,
        "events": len(events),
    }
    with open("last_run.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    print("Wrote {} events to {}".format(len(events), args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
