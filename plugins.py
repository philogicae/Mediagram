from pythonopensubtitles.opensubtitles import OpenSubtitles
from rarbgapi import RarbgAPI


class SrtSearch:
    LBD = lambda sub: sub['nb_downloads']

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
            format=sub['SubFormat']
        ) for sub in subtitles]
        return sorted(filtered, key=self.LBD, reverse=True)

    def download(self, id, name, path):
        self.api.download_subtitles([id], override_filenames={
                                    id: name}, output_directory=path)


class TorrentSearch:
    def __init__(self):
        self.api = RarbgAPI()

    def query(self, query):
        torrents = self.api.search(
            search_string=query, extended_response=True, sort='seeders')
        return [dict(
            name=t.filename,
            peers=f'{t.seeders}/{t.leechers}',
            size=f'{t.size / 2**30:.2f} Go',
            magnet=t.download
        ) for t in torrents]
