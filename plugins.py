from pythonopensubtitles.opensubtitles import OpenSubtitles
from rarbgapi import RarbgAPI


class SubtitlesSearch:
    def __init__(self, user, password):
        self.api = OpenSubtitles()
        self.api.login(user, password)

    def query(self, query, lang='fre', max_results=5):
        subtitles = self.api.search_subtitles(
            [{'query': query, 'sublanguageid': lang}])
        remap = lambda sub: dict(
            id=sub['IDSubtitleFile'],
            name=sub['MovieReleaseName'],
            nb_downloads=int(sub['SubDownloadsCnt']),
            lang=sub['SubLanguageID'],
            ext=sub['SubFormat'])
        remapped = list(map(remap, subtitles))
        return sorted(remapped, key=lambda sub: sub['nb_downloads'], reverse=True)[:max_results]

    def download(self, sub, name, path):
        ids, names = [sub['id']], {sub['id']: f"{name}.{sub['ext']}"}
        return self.api.download_subtitles(ids, names, path, extension=sub['ext'])


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
