import os
import requests
import json
from urllib.parse import urlencode


class OpenSubtitlesV2:
    def __init__(self):
        self.login_token = None
        self.user_downloads_remaining = None

    def login(self, user, password, apikey):
        self.user = user
        self.password = password
        self.apikey = apikey

        login_url = "https://api.opensubtitles.com/api/v1/login"
        login_headers = {'api-key': self.apikey,
                         'content-type': 'application/json'}
        login_body = {'username': self.user, 'password': self.password}
        try:
            login_response = requests.post(
                login_url, data=json.dumps(login_body), headers=login_headers)
            login_response.raise_for_status()
            login_json_response = login_response.json()
            self.login_token = login_json_response['token']
        except requests.exceptions.HTTPError as httperr:
            raise Exception(httperr)
        except requests.exceptions.RequestException as reqerr:
            raise Exception("Failed to login: " + reqerr)
        except ValueError as e:
            raise Exception("Failed to parse login JSON response: " + e)

        user_url = "https://api.opensubtitles.com/api/v1/infos/user"
        user_headers = {'api-key': self.apikey,
                        'authorization': self.login_token}
        try:
            user_response = requests.get(user_url, headers=user_headers)
            user_response.raise_for_status()
            user_json_response = user_response.json()
            self.user_downloads_remaining = user_json_response['data']['remaining_downloads']
        except requests.exceptions.HTTPError as httperr:
            raise Exception(httperr)
        except requests.exceptions.RequestException as reqerr:
            raise Exception("Failed to login: " + reqerr)
        except ValueError as e:
            raise Exception("Failed to parse user JSON response: " + e)

    def search_subtitles(self, filename, sublanguage):
        try:
            query_params = {
                'foreign_parts_only': 'exclude',
                'languages': sublanguage.lower(),
                'order_by': 'download_count',
                'order_direction': 'desc',
                'query': filename.lower()
            }
            query_params = urlencode(query_params)
            query_url = "https://api.opensubtitles.com/api/v1/subtitles"
            query_headers = {'api-key': self.apikey}
            query_response = requests.get(
                query_url, params=query_params, headers=query_headers)
            query_response.raise_for_status()
            query_json_response = query_response.json()
            if 'data' in query_json_response:
                return query_json_response['data']
        except requests.exceptions.HTTPError as httperr:
            raise Exception(httperr)
        except requests.exceptions.RequestException as reqerr:
            raise Exception("Failed to login: " + reqerr)
        except ValueError as e:
            raise Exception(
                "Failed to parse search_subtitle JSON response: " + e)

    def download_subtitle(self, id, name, path):
        download_url = "https://api.opensubtitles.com/api/v1/download"
        download_headers = {'api-key': self.apikey,
                            'authorization': self.login_token,
                            'content-type': 'application/json'}
        download_body = {'file_id': id}
        if self.user_downloads_remaining > 0:
            try:
                download_response = requests.post(download_url, data=json.dumps(
                    download_body), headers=download_headers)
                download_json_response = download_response.json()
                self.user_downloads_remaining = download_json_response['remaining']
                download_link = download_json_response['link']
                download_remote_file = requests.get(download_link)
                file = os.path.join(path, name)
                with open(file, 'wb') as f:
                    f.write(download_remote_file.content)
                    return {id: file}
            except requests.exceptions.HTTPError as httperr:
                raise Exception(httperr)
            except requests.exceptions.RequestException as reqerr:
                raise Exception("Failed to login: " + reqerr)
            except ValueError as e:
                raise Exception(
                    "Failed to parse search_subtitle JSON response: " + e)
        else:
            print("Download limit reached. Wait for your quota to reset (~24hrs)")
