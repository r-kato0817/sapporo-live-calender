#!/usr/bin/env python3
"""Sapporo live house schedules -> iCalendar (.ics) generator.

Scrapes the official schedule pages of Sapporo live houses and writes a
single ICS file that can be subscribed to in Google Calendar.

Sources:
  - PRECIOUS HALL : http://www.precioushall.com/schedule/
  - SOUND CRUE    : https://soundcrue.com/schedule/
"""

import argparse
import datetime
import html
import json
import re
import sys
import time
import urllib.request

USER_AGENT = "Mozilla/5.0 (compatible; sapporo-live-cal/1.0)"
TIMEOUT = 30

CALTZ = "Asia/Tokyo"
CALNAME = "Sapporo Live Schedule"
CALDESC = "PRECIOUS HALL & SOUND CRUE (Sapporo) latest live schedule"

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

SOURCES = {
    "precioushall": {
        "name": "PRECIOUS HALL",
        "location": "PRECIOUS HALL (Parade B2F, 札幌市中央区南2条西3丁目)",
        "uid_domain": "precioushall.com",
        "default_duration": datetime.timedelta(hours=6),
        "list_url": "http://www.precioushall.com/schedule/",
    },
    "soundcrue": {
        "name": "SOUND CRUE",
        "location": "SOUND CRUE (札幌市中央区大通東2丁目15-1-2)",
        "uid_domain": "soundcrue.com",
        "default_duration": datetime.timedelta(hours=3),
        "list_url": "https://soundcrue.com/schedule/",
    },
}

SOURCE_ORDER = ["precioushall", "soundcrue"]


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


# --- PRECIOUS HALL ----------------------------------------------------------

def parse_precioushall_list(text: str) -> list:
    events = []
    for m in re.finditer(
        r'<div class="sp_flyer" id="(?P<dateid>\d{8})">.*?'
        r'<div class="textblock">(?P<body>.*?)</div>\s*</div>',
        text,
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
            "source": "precioushall",
            "dateid": dateid,
            "year": year,
            "month": month,
            "day": day,
            "title": title,
            "subtitle": subtitle,
            "details": details,
            "detail_url": SOURCES["precioushall"]["list_url"] + path,
        })
    return events


def parse_precioushall_detail(text: str):
    adm = None
    start_hm = None
    m = re.search(r'<p class="fee">(.*?)</p>', text, re.S)
    if m:
        adm = strip_tags(m.group(1))
        adm = re.split(r"PRECIOUS HALL", adm, flags=re.I)[0].strip()
        adm = re.sub(r"^\s*ADM\s*:", "", adm).strip()
        tm = re.search(r"(\d{1,2}):(\d{2})", adm)
        if tm:
            start_hm = (int(tm.group(1)), int(tm.group(2)))
    return {"fee": adm, "start_hm": start_hm}


# --- SOUND CRUE -------------------------------------------------------------

def parse_soundcrue_list(text: str) -> list:
    mm = re.search(r'<h2 class="this_month">\s*(\d{4})\.<span>(\d{2})</span>', text)
    if not mm:
        return []
    year, month = int(mm.group(1)), int(mm.group(2))

    events = []
    for m in re.finditer(r'<li class="schedule_li list_cont">(.*?)</li>', text, re.S):
        body = m.group(1)
        am = re.search(r'<a href="([^"]+)">', body)
        if not am:
            continue
        detail_url = am.group(1)

        dm = re.search(r'<p class="schedule_date">\s*(\d{1,2})\s*</p>', body)
        if not dm:
            continue
        day = int(dm.group(1))

        tmm = re.search(r'<p class="schedule_title">(.*?)</p>', body, re.S)
        title = strip_tags(tmm.group(1)) if tmm else ""

        names = []
        am2 = re.search(r'<p class="past_act">(.*?)</p>', body, re.S)
        if am2:
            for piece in re.split(r"<br\s*/?>", am2.group(1)):
                piece = strip_tags(piece)
                if piece:
                    names.append(piece)

        events.append({
            "source": "soundcrue",
            "dateid": "{:04d}{:02d}{:02d}".format(year, month, day),
            "year": year,
            "month": month,
            "day": day,
            "title": title,
            "subtitle": None,
            "details": [{"label": "LINEUP", "value": "\n".join(names)}] if names else [],
            "detail_url": detail_url,
        })
    return events


def parse_soundcrue_detail(text: str):
    fee = None
    open_hm = None
    start_hm = None
    tm = re.search(r'<p class="schedule_time">(.*?)</p>', text, re.S)
    if tm:
        time_text = strip_tags(tm.group(1))
        mt = re.search(
            r"open\s*(\d{1,2}):(\d{2})\s*/\s*start\s*(\d{1,2}):(\d{2})", time_text)
        if mt:
            open_hm = (int(mt.group(1)), int(mt.group(2)))
            start_hm = (int(mt.group(3)), int(mt.group(4)))
        else:
            mo = re.search(r"(\d{1,2}):(\d{2})", time_text)
            if mo:
                start_hm = (int(mo.group(1)), int(mo.group(2)))
    pm = re.search(r'<p class="schedule_price">(.*?)</p>', text, re.S)
    if pm:
        fee = strip_tags(pm.group(1))
    return {"fee": fee, "open_hm": open_hm, "start_hm": start_hm}


# --- shared -----------------------------------------------------------------

DETAIL_PARSERS = {
    "precioushall": parse_precioushall_detail,
    "soundcrue": parse_soundcrue_detail,
}


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
    limit = 75
    while i < len(raw):
        end = min(i + limit, len(raw))
        if end < len(raw) and (raw[end] & 0xC0) == 0x80:
            while end > i and (raw[end] & 0xC0) == 0x80:
                end -= 1
        if end <= i:
            end = i + 1
        parts.append(raw[i:end].decode("utf-8"))
        i = end
        limit = 74
    out = parts[0]
    for p in parts[1:]:
        out += "\r\n " + p
    return out


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def hhmm(hm) -> str:
    return "{:02d}:{:02d}".format(*hm)


def build_description(ev: dict, info: dict) -> str:
    sections = []
    if ev["subtitle"]:
        sections.append("Subtitle: " + ev["subtitle"])
    if ev["details"]:
        for d in ev["details"]:
            if "\n" in d["value"]:
                sections.append("{}:\n{}".format(d["label"], d["value"]))
            else:
                sections.append("{}: {}".format(d["label"], d["value"]))
    if ev.get("fee"):
        sections.append("TICKET: " + ev["fee"])
    if ev.get("open_hm"):
        sections.append("OPEN: " + hhmm(ev["open_hm"]))
    if ev.get("start_hm"):
        sections.append(
            "START: {} (end time not published, ~{}h assumed)"
            .format(hhmm(ev["start_hm"]), info["default_duration"].seconds // 3600))
    sections.append("Details: " + ev["detail_url"])
    return "\n\n".join(sections)


def build_event(ev: dict, info: dict) -> str:
    uid = "{slug}-{dateid}-{slug2}@{domain}".format(
        slug=ev["source"], dateid=ev["dateid"], slug2=slugify(ev["title"]),
        domain=info["uid_domain"])
    d = datetime.date(ev["year"], ev["month"], ev["day"])
    summary = "{} @ {}".format(ev["title"], info["name"])

    lines = ["BEGIN:VEVENT"]
    lines.append("UID:" + uid)
    lines.append("DTSTAMP:" + now_utc())
    lines.append("SUMMARY:" + esc(summary))
    lines.append("LOCATION:" + esc(info["location"]))
    if ev.get("start_hm"):
        start_dt = datetime.datetime(
            ev["year"], ev["month"], ev["day"],
            ev["start_hm"][0], ev["start_hm"][1])
        end_dt = start_dt + info["default_duration"]
        lines.append("DTSTART;TZID=Asia/Tokyo:" + start_dt.strftime("%Y%m%dT%H%M%S"))
        lines.append("DTEND;TZID=Asia/Tokyo:" + end_dt.strftime("%Y%m%dT%H%M%S"))
    else:
        lines.append("DTSTART;VALUE=DATE:" + d.strftime("%Y%m%d"))
        lines.append("DTEND;VALUE=DATE:" + (d + datetime.timedelta(days=1)).strftime("%Y%m%d"))
    lines.append("DESCRIPTION:" + esc(build_description(ev, info)))
    lines.append("URL:" + ev["detail_url"])
    lines.append("END:VEVENT")
    return "\r\n".join(fold(ln) for ln in lines)


def build_calendar(events: list) -> str:
    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//sapporo-live-calendar//sapporo-live//JA",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + CALNAME,
        "X-WR-CALDESC:" + CALDESC,
        "X-WR-TIMEZONE:" + CALTZ,
        VTIMEZONE,
    ]
    body = [build_event(ev, SOURCES[ev["source"]]) for ev in events]
    parts = header + body + ["END:VCALENDAR", ""]
    return "\r\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="sapporo-live.ics")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="delay in seconds between detail-page requests")
    parser.add_argument("--source", action="append",
                        help="only fetch this source (repeatable); default: all")
    args = parser.parse_args()

    selected = args.source or SOURCE_ORDER
    counts = {}
    events = []

    for key in selected:
        if key not in SOURCES:
            print("ERROR: unknown source '{}'".format(key), file=sys.stderr)
            return 1
        info = SOURCES[key]
        try:
            print("Fetching schedule page: " + info["list_url"])
            parsed = LIST_PARSERS[key](fetch(info["list_url"]))
        except Exception as exc:
            print("ERROR: failed to fetch {} list page: {}".format(info["name"], exc),
                  file=sys.stderr)
            return 1

        seen = set()
        for ev in parsed:
            if ev["dateid"] in seen:
                continue
            seen.add(ev["dateid"])
            try:
                print("Fetching detail: {}".format(ev["detail_url"]))
                extra = DETAIL_PARSERS[key](fetch(ev["detail_url"]))
                ev.update(extra)
                time.sleep(args.delay)
            except Exception as exc:
                print("WARN: failed to fetch detail page {}: {}".format(
                    ev["detail_url"], exc), file=sys.stderr)
            events.append(ev)

        counts[key] = sum(1 for ev in events if ev["source"] == key)

    cal = build_calendar(events)
    with open(args.output, "w", encoding="utf-8", newline="") as fh:
        fh.write(cal)

    summary = {
        "last_run": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds"),
        "sources": {SOURCES[k]["name"]: counts[k]
                    for k in SOURCE_ORDER if k in selected},
        "total_events": len(events),
    }
    with open("last_run.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    print("Wrote {} events to {}".format(len(events), args.output))
    return 0


LIST_PARSERS = {
    "precioushall": parse_precioushall_list,
    "soundcrue": parse_soundcrue_list,
}


if __name__ == "__main__":
    sys.exit(main())
