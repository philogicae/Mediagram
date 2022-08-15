from pythonopensubtitles.opensubtitles import OpenSubtitles
from rarbgapi import RarbgAPI


class SubtitlesSearch:
    def __init__(self, user, password):
        self.api = OpenSubtitles()
        self.api.login(user, password)

    def query(self, query, lang='fre'):
        subtitles = self.api.search_subtitles(
            [{'query': query, 'sublanguageid': lang}])
        filtered = [dict(
            id=sub['IDSubtitleFile'],
            name=sub['MovieReleaseName'],
            nb_downloads=int(sub['SubDownloadsCnt']),
            lang=sub['SubLanguageID'],
            ext=sub['SubFormat']
        ) for sub in subtitles]
        return sorted(filtered, key=lambda sub: sub['nb_downloads'], reverse=True)[:10]

    def download(self, sub, name, path):
        ids, names = [sub['id']], {sub['id']: f"{name}.{sub['ext']}"}
        return self.api.download_subtitles(ids, names, path, extension=sub['ext'])


class TorrentSearch:
    CATEGORIES = [14, 48, 17, 44, 45, 50, 51, 52, 54, 42, 46, 18, 41, 49]

    def __init__(self):
        self.api = RarbgAPI()

    def query(self, query):
        torrents = self.api.search(
            search_string=query, extended_response=True, sort='seeders', categories=self.CATEGORIES)
        return [dict(
            name=t.filename,
            peers=f'{t.seeders}/{t.leechers}',
            size=f'{t.size / 2**30:.2f} Go',
            magnet=t.download
        ) for t in torrents if t.seeders > 1][:10]
