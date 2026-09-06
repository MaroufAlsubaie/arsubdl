"""arSUBDL provider for Bazarr+ Provider Hub."""

import base64
import hashlib
import json
import urllib.parse
import urllib.request
import zipfile
import io


API_URL = "https://api.subdl.com/api/v2/subtitles/search"
DOWNLOAD_URL = "https://dl.subdl.com"

PROVIDER_ID = "arsubdl"


class ArSubDLProvider:

    def _request(self, params):
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{API_URL}?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": "Bazarr arSUBDL",
            },
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def search(self, video, languages, config):
        api_key = config["api_key"]

        if video.get("kind") != "episode":
            return []

        season = video.get("season")
        episode = video.get("absolute_episode") or video.get("episode")

        language_codes = []

        for language in languages:
            code = language.get("alpha3")

            if code == "ara":
                language_codes.append("AR")
            elif code == "eng":
                language_codes.append("EN")

        if not language_codes:
            return []

        params = {
            "api_key": api_key,
            "tmdb_id": video.get("tmdb_id"),
            "type": "tv",
            "season": season,
            "episode": episode,
            "languages": ",".join(language_codes),
            "unpack": 1,
        }

        data = self._request(params)

        results = []

        for item in data.get("subtitles", []):
            language = item.get("language")

            if language == "AR":
                alpha3 = "ara"
            elif language == "EN":
                alpha3 = "eng"
            else:
                continue

            unpack_files = item.get("unpack_files") or []

            if unpack_files:
                for child in unpack_files:
                    if child.get("episode") != episode:
                        continue

                    results.append({
                        "provider": PROVIDER_ID,
                        "id": child.get("file_n_id") or child.get("name"),
                        "language": {
                            "alpha3": alpha3,
                            "hi": bool(child.get("hi", False)),
                            "forced": False,
                        },
                        "release_info": item.get("name", ""),
                        "filename": child.get("name", ""),
                        "matches": [
                            "series",
                            "season",
                            "episode",
                        ],
                        "score": 100,
                        "score_without_hash": 100,
                        "score_out_of": 100,
                        "hash_verifiable": False,
                        "hearing_impaired_verifiable": True,
                        "hearing_impaired": bool(child.get("hi", False)),
                        "display": {
                            "source": "SubDL",
                            "uploader": item.get("author", ""),
                            "page_link": "https://subdl.com",
                        },
                        "provider_payload": {
                            "url": child.get("url"),
                            "format": child.get("format", "srt"),
                        },
                    })

            else:
                results.append({
                    "provider": PROVIDER_ID,
                    "id": item.get("name"),
                    "language": {
                        "alpha3": alpha3,
                        "hi": bool(item.get("hi", False)),
                        "forced": False,
                    },
                    "release_info": item.get("name", ""),
                    "filename": item.get("name", ""),
                    "matches": [
                        "series",
                        "season",
                        "episode",
                    ],
                    "score": 100,
                    "score_without_hash": 100,
                    "score_out_of": 100,
                    "hash_verifiable": False,
                    "hearing_impaired_verifiable": True,
                    "hearing_impaired": bool(item.get("hi", False)),
                    "display": {
                        "source": "SubDL",
                        "uploader": item.get("author", ""),
                        "page_link": "https://subdl.com",
                    },
                    "provider_payload": {
                        "url": item.get("url"),
                        "format": "srt",
                    },
                })

        return results

    def download(self, provider_payload, language, config):
        url = provider_payload["url"]

        if not url.startswith("http"):
            url = DOWNLOAD_URL + url

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Bazarr arSUBDL",
            },
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()

        if zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                files = [
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(
                        (".srt", ".ass", ".ssa", ".vtt", ".sub")
                    )
                ]

                if not files:
                    raise ValueError("No subtitle found in SubDL archive")

                data = archive.read(files[0])

        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

        return {
            "content_b64": base64.b64encode(data).decode("ascii"),
            "content_sha256": hashlib.sha256(data).hexdigest(),
            "content_type": "text/plain",
            "format": provider_payload.get("format", "srt"),
            "empty": False,
        }