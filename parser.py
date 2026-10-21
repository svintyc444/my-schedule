import datetime
import re
import requests
from bs4 import BeautifulSoup

# Базовый URL для вашей группы
BASE_URL = "https://rasp.unecon.ru/raspisanie_grp.php?g=14100"

# Официальная сетка пар СПбГЭУ
BELL_SCHEDULE = {
    1: ("09:00", "10:35"),
    2: ("10:45", "12:20"),
    3: ("13:00", "14:35"),
    4: ("14:45", "16:20"),
    5: ("16:30", "18:05"),
    6: ("18:15", "19:50"),
    7: ("20:00", "21:35"),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

def parse_week(url):
    response = requests.get(url, headers=HEADERS)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    events = []
    current_date = None

    # Поиск по всем строкам таблицы расписания
    rows = soup.find_all("tr")

    for row in rows:
        text = row.get_text(separator=" ", strip=True)
        if not text:
            continue

        # Поиск даты дня (например: "21.10.2024" или "Понедельник, 21.10")
        date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
        if date_match:
            d, m, y = date_match.groups()
            current_date = f"{y}{m}{d}"

        if not current_date:
            continue

        # Извлечение времени или номера пары
        time_match = re.search(r"(\d{1,2}:\d{2})\s*[-—–]\s*(\d{1,2}:\d{2})", text)
        start_time_str = None
        end_time_str = None

        if time_match:
            sh, eh = time_match.groups()
            start_time_str = sh.replace(":", "").zfill(4) + "00"
            end_time_str = eh.replace(":", "").zfill(4) + "00"
        else:
            # Проверка по номеру пары в начале строки
            pair_match = re.search(r"^(\d)\s*пара", text, re.IGNORECASE)
            if pair_match:
                p_num = int(pair_match.group(1))
                if p_num in BELL_SCHEDULE:
                    s, e = BELL_SCHEDULE[p_num]
                    start_time_str = s.replace(":", "") + "00"
                    end_time_str = e.replace(":", "") + "00"

        # Если в строке обнаружена пара
        cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        if start_time_str and len(cols) >= 2:
            row_content = " ".join(cols[1:])
            if len(row_content) < 5 or "нет пар" in row_content.lower():
                continue

            # Поиск аудитории
            room_match = re.search(r"(?:ауд\.?|каб\.?)\s*([\w\d\-\/]+)", row_content, re.IGNORECASE)
            room = room_match.group(1) if room_match else "Не указана"

            # Очистка названия предмета для заголовка
            title_clean = re.sub(r"(?:ауд\.?|каб\.?)\s*[\w\d\-\/]+", "", row_content, flags=re.IGNORECASE)
            summary = " ".join(title_clean.split()[:6])

            events.append({
                "summary": summary,
                "location": f"ауд. {room}",
                "description": row_content,
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

    linesappend("END:VCALENDAR")
    return "\r\n".join(lines)

if __name__ == "__main__":
    # Парсим указанную неделю (w=9) и при необходимости соседние
    target_url = "https://rasp.unecon.ru/raspisanie_grp.php?g=14100&w=9"
    parsed = parse_week(target_url)

    ics = generate_ics(parsed)
    with open("schedule.ics", "w", encoding="utf-8") as f:
        f.write(ics)
        
    print(f"Готово! Добавлено занятий: {len(parsed)}")
