import asyncio
import aiohttp
import json
import qrcode
from qrcode.constants import ERROR_CORRECT_M
from io import BytesIO
from pathlib import Path
from re import search, fullmatch
from rapidfuzz import process
from datetime import datetime
from maxapi.types import InputMediaBuffer


CITY_DATA_PATH = Path(__file__).resolve().with_name('citys.json')


with CITY_DATA_PATH.open(encoding='UTF-8') as file:
    data = json.load(file)

    citys = {i['city'].lower() for i in data}


def extract_contact(string: str) -> int:
    return int(search(r'TEL;TYPE=cell:(\d+)', string).group(1).strip())


def check_full_name(full_name: str) -> bool:
    return bool(fullmatch(r'^[а-я]+ [а-я]+ [а-я]+$', full_name.strip().lower()))


async def get_address_by_coords(lat: float, lon: float):
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1,
        "accept-language": "ru"
    }
    
    headers = {
        "User-Agent": "MaxBot"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()

    address = data.get("address", {})

    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("hamlet")
        or address.get("county")
    )

    return {
        "city": city,
        "full_address": data.get("display_name"),
        "raw": data
    }

async def get_address_by_coords(lat: float, lon: float) -> dict | None:
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1,
        "accept-language": "ru"
    }
    headers = {
        "User-Agent": "MaxBot"
    }
    timeout = aiohttp.ClientTimeout(total=10)

    try:
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()

        address = data.get("address", {})

        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("county")
        )

        if not city:
            return None

        return {
            "city": city,
            "full_address": data.get("display_name"),
            "raw": data
        }

    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
        return None


def get_similar_city(city_name: str) -> tuple[str, float]:
    return process.extract(city_name.strip().lower(), citys)[0][:-1]


def check_date(str_date: str) -> bool:
    try:
        return datetime.strptime(str_date, '%d.%m.%Y').date() <= datetime.now().date()
    except BaseException:
        return False


def convert_to_standart_date(str_date: str) -> str:
    return str(datetime.strptime(str_date, '%d.%m.%Y').date())


def build_qr_bytes(data: str) -> InputMediaBuffer:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="white", back_color="blue")

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    qr = InputMediaBuffer(
        buffer=buffer.getvalue(),
        filename="qrcode.png"
    )

    return qr


async def get_qr(max_user_id: int) -> InputMediaBuffer:
    data = str(max_user_id)
    return await asyncio.to_thread(build_qr_bytes, data)
