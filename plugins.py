from pythonopensubtitles.opensubtitles import OpenSubtitles
from opensubtitles_v2 import OpenSubtitlesV2
from rarbgapi import RarbgAPI


class SubtitlesSearch:
    def __init__(self, user, password):
        self.api = OpenSubtitles()
        self.api.login(user, password)

    def query(self, query, lang='fre', max_results=5):
        subtitles = self.api.search_subtitles(
            [{'query': query, 'sublanguageid': lang}])
        if subtitles:
            remap = lambda sub: dict(
                id=sub['IDSubtitleFile'],
                name=sub['MovieReleaseName'],
                nb_downloads=int(sub['SubDownloadsCnt']),
                lang=sub['SubLanguageID'][:2],
                ext=sub['SubFormat'])
            remapped = list(map(remap, subtitles))
            return sorted(remapped, key=lambda sub: sub['nb_downloads'], reverse=True)[:max_results]

    def download(self, sub, name, path):
        id, name = [sub['id']], {
            sub['id']: f"{name}.{sub['ext']}"}
        return self.api.download_subtitles(id, name, path, extension=sub['ext'])


class SubtitlesSearchV2:
    def __init__(self, user, password, apikey):
        self.api = OpenSubtitlesV2()
        self.api.login(user, password, apikey)

    def query(self, query, lang='fre', max_results=5):
        lang = lang[:2]
        subtitles = self.api.search_subtitles(query, lang)
        if subtitles:
            remap = lambda sub: dict(
                id=sub['attributes']['files'][0]['file_id'],
                name=sub['attributes']['files'][0]['file_name'] if 'file_name' in sub['attributes']['files'][0] else sub['attributes']['release'],
                nb_downloads=sub['attributes']['download_count'],
                lang=sub['attributes']['language'],
                ext='srt')
            return list(map(remap, subtitles[:max_results]))

    def download(self, sub, name, path):
        id, name = sub['id'], f"{name}.{sub['ext']}"
        return self.api.download_subtitle(id, name, path)


class TorrentSearch:
    CATEGORIES = [14, 48, 17, 44, 45, 50, 51, 52, 54, 42, 46, 18, 41, 49]

    def __init__(self):
        self.api = RarbgAPI()

    def query(self, query, min_seeders=5, max_results=5):
        torrents = self.api.search(
            search_string=query, extended_response=True, sort='seeders', categories=self.CATEGORIES, limit=10)
        filt = lambda t: t.seeders > min_seeders
        remap = lambda t: dict(
            name=t.filename,
            seeders=t.seeders,
            leechers=t.leechers,
            size=round(t.size / 2**30, 2),
            category=t.category,
            date=t.pubdate[:-6],
            magnet=t.download)
        filtered = filter(filt, torrents)
        remapped = list(map(remap, filtered))
        return remapped[:max_results]


if __name__ == '__main__':
    from rich import print
    from os import getenv
    from dotenv import load_dotenv
    load_dotenv()
    ost_user = getenv("OST_USER")
    ost_pass = getenv("OST_PASS")
    ost_apikey = getenv("OST_API_KEY")
    ss = SubtitlesSearchV2(ost_user, ost_pass, ost_apikey)
    print(ss.query("The last of us s01e03", lang="eng", max_results=5))
