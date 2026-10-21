import datetime
import re
import requests
from bs4 import BeautifulSoup

# URL расписания вашей группы
URL = "https://rasp.unecon.ru/raspisanie_grp.php?g=14100"

# Стандартная сетка пар СПбГЭУ
BELL_SCHEDULE = {
    1: ("09:00", "10:35"),
    2: ("10:50", "12:25"),
    3: ("12:40", "14:15"),
    4: ("14:30", "16:00"),
    5: ("16:10", "17:40"),
    6: ("18:30", "20:00"),
    7: ("20:10", "21:40"),
}


def parse_schedule():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(URL, headers=headers)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    current_date = None

    # Таблица расписания в СПбГЭУ строится построчно
    # Дни недели обычно идут заголовками или отдельными строками
    rows = soup.find_all(["tr", "div", "li"])

    for row in rows:
        text = row.get_text(separator=" ", strip=True)

        # 1. Поиск даты (форматы: "ДД.ММ.ГГГГ" или "Понедельник, 15 октября")
        date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
        if date_match and ("день" in text.lower() or len(text) < 40):
            day, month, year = date_match.groups()
            current_date = f"{year}{month}{day}"
            continue

        if not current_date:
            continue

        # 2. Определение номера пары (1-7) или времени
        pair_num = None
        time_match = re.search(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", text)
        pair_match = re.search(r"^(\d)\s*пара|\b(\d)\s*п\b", text, re.IGNORECASE)

        start_time_str = None
        end_time_str = None

        if time_match:
            sh, sm, eh, em = time_match.groups()
            start_time_str = f"{int(sh):02d}{sm}00"
            end_time_str = f"{int(eh):02d}{em}00"
        elif pair_match:
            pair_num = int(pair_match.group(1) or pair_match.group(2))
            if pair_num in BELL_SCHEDULE:
                s, e = BELL_SCHEDULE[pair_num]
                start_time_str = s.replace(":", "") + "00"
                end_time_str = e.replace(":", "") + "00"

        # Если нашли предмет и строку с парой
        if start_time_str and ("лек" in text.lower() or "прак" in text.lower() or "ауд" in text.lower() or len(text) > 15):
            # Извлекаем аудиторию (обычно после слова "ауд." или трех-четырехзначное число)
            room_match = re.search(r"(?:ауд\.?|каб\.?)\s*([\w\d\-\/]+)", text, re.IGNORECASE)
            room = room_match.group(1) if room_match else "Уточняется"

            # Очищаем название дисциплины
            clean_text = re.sub(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", "", text)
            clean_text = re.sub(r"(?:ауд\.?|каб\.?)\s*[\w\d\-\/]+", "", clean_text, flags=re.IGNORECASE)
            summary = " ".join(clean_text.split()[:7])  # Компактный заголовок

            events.append({
                "summary": summary,
                "location": f"ауд. {room}",
                "description": text,
                "date": current_date,
                "start_time": start_time_str,
                "end_time": end_time_str,
            })

    return events


def generate_ics(events):
    now_stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UNECON Schedule Sync//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Расписание СПбГЭУ",
        "X-WR-TIMEZONE:Europe/Moscow",
    ]

    for idx, ev in enumerate(events):
        dtstart = f"{ev['date']}T{ev['start_time']}"
        dtend = f"{ev['date']}T{ev['end_time']}"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:unecon-{ev['date']}-{ev['start_time']}-{idx}@schedule",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;TZID=Europe/Moscow:{dtstart}",
            f"DTEND;TZID=Europe/Moscow:{dtend}",
            f"SUMMARY:{ev['summary']}",
            f"LOCATION:{ev['location']}",
            f"DESCRIPTION:{ev['description']}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


if __name__ == "__main__":
    parsed = parse_schedule()
    ics = generate_ics(parsed)
    with open("schedule.ics", "w", encoding="utf-8") as f:
        f.write(ics)
    print(f"Готово! Добавлено занятий: {len(parsed)}")
