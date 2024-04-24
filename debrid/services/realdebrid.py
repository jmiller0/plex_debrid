#import modules
from base import *
from ui.ui_print import *
import releases

# (required) Name of the Debrid service
name = "Real Debrid"
short = "RD"
# (required) Authentification of the Debrid service, can be oauth aswell. Create a setting for the required variables in the ui.settings_list. For an oauth example check the trakt authentification.
api_key = ""
name_dict = {}
# Define Variables
session = requests.Session()
errors = [
    [202," action already done"],
    [400," bad Request (see error message)"],
    [403," permission denied (infringing torrent or account locked or not premium)"],
    [503," service unavailable (see error message)"],
    [404," wrong parameter (invalid file id(s)) / unknown ressource (invalid id)"],
    ]

def setup(cls, new=False):
    from debrid.services import setup
    setup(cls,new)

# Error Log
def logerror(response):
    if not response.status_code in [200,201,204]:
        desc = ""
        for error in errors:
            if response.status_code == error[0]:
                desc = error[1]
        ui_print("[realdebrid] error: (" + str(response.status_code) + desc + ") " + str(response.content), debug=ui_settings.debug)
    if response.status_code == 401:
        ui_print("[realdebrid] error: (401 unauthorized): realdebrid api key does not seem to work. check your realdebrid settings.")
    if response.status_code == 403:
        ui_print("[realdebrid] error: (403 unauthorized): You may have attempted to add an infringing torrent or your realdebrid account is locked or you dont have premium.")

# Get Function
def get(url, return_generic_response=False):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36','authorization': 'Bearer ' + api_key}
    response = None
    try:
        response = session.get(url, headers=headers)
        logerror(response)
        if return_generic_response:
            return response
        else:
            response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("[realdebrid] error: (json exception): " + str(e), debug=ui_settings.debug)
        response = None
    return response

# Post Function
def post(url, data):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36','authorization': 'Bearer ' + api_key}
    response = None
    try:
        response = session.post(url, headers=headers, data=data)
        logerror(response)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        if hasattr(response,"status_code"):
            if response.status_code >= 300:
                ui_print("[realdebrid] error: (json exception): " + str(e), debug=ui_settings.debug)
        else:
            ui_print("[realdebrid] error: (json exception): " + str(e), debug=ui_settings.debug)
        response = None
    return response

# Delete Function
def delete(url):
    ui_print(f"[realdebrid] delete: {url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36','authorization': 'Bearer ' + api_key}
    try:
        response = requests.delete(url, headers=headers)
        if response.status_code != 204:
                ui_print("[realdebrid] error: (delete status code): " + str(response.status_code), debug=ui_settings.debug)
        time.sleep(1)
    except Exception as e:
        ui_print("[realdebrid] error: (delete exception): " + str(e), debug=ui_settings.debug)
        None
    return None

# Object classes
class file:
    def __init__(self, id, name, size, wanted_list, unwanted_list):
        self.id = id
        self.name = name
        self.size = size / 1000000000
        self.match = ''
        wanted = False
        unwanted = False
        for key, wanted_pattern in wanted_list:
            if wanted_pattern.search(self.name):
                wanted = True
                self.match = key
                break

        if not wanted:
            for key, unwanted_pattern in unwanted_list:
                if unwanted_pattern.search(self.name) or self.name.endswith('.exe') or self.name.endswith('.txt'):
                    unwanted = True
                    break

        self.wanted = wanted
        self.unwanted = unwanted

    def __eq__(self, other):
        return self.id == other.id

class version:
    def __init__(self, files):
        self.files = files
        self.needed = 0
        self.wanted = 0
        self.unwanted = 0
        self.size = 0
        for file in self.files:
            self.size += file.size
            if file.wanted:
                self.wanted += 1
            if file.unwanted:
                self.unwanted += 1

# (required) Download Function.
def download(element, stream=True, query='', force=False):
    cached = element.Releases

    if query == '':
        query = element.deviation()
    wanted = [query]
    if not isinstance(element, releases.release):
        wanted = element.files()
    for release in cached[:]:
        # if release matches query
        try:
            match = regex.match(query, release.title,regex.I) or force
        except Exception as e:
            ui_print('[realdebrid] error: could not match query: ' + query + ' for release: ' + release.title, ui_settings.debug)
            match = False
        if match:
            # if check_exists(match.string):
            #     ui_print(f"[realdebrid] torrent with id {match.string} exists")
            #     return False
            if stream:
                release.size = 0
                for version in release.files:
                    if hasattr(version, 'files'):
                        if len(version.files) > 0 and version.wanted > len(wanted) / 2 or force:
                            cached_ids = []
                            for file in version.files:
                                cached_ids += [file.id]
                            # post magnet to real debrid
                            try:
                                response = post('https://api.real-debrid.com/rest/1.0/torrents/addMagnet',{'magnet': str(release.download[0])})
                                torrent_id = str(response.id)
                            except:
                                ui_print('[realdebrid] error: could not add magnet for release: ' + release.title, ui_settings.debug)
                                continue

                            response = post('https://api.real-debrid.com/rest/1.0/torrents/selectFiles/' + torrent_id,{'files': str(','.join(cached_ids))})
                            response = get('https://api.real-debrid.com/rest/1.0/torrents/info/' + torrent_id)
                            actual_title = ""
                            if len(response.links) == len(cached_ids):
                                actual_title = response.filename
                                release.download = response.links
                            else:
                                if response.status in ["queued","magnet_convesion","downloading","uploading"]:
                                    if hasattr(element,"version"):
                                        debrid_uncached = True
                                        for i,rule in enumerate(element.version.rules):
                                            if (rule[0] == "cache status") and (rule[1] == 'requirement' or rule[1] == 'preference') and (rule[2] == "cached"):
                                                debrid_uncached = False
                                        if debrid_uncached:
                                            import debrid as db
                                            release.files = version.files
                                            db.downloading += [element.query() + ' [' + element.version.name + ']']
                                            ui_print('[realdebrid] adding uncached release: ' + release.title)
                                            return True
                                else:
                                    ui_print('[realdebrid] error: selecting this cached file combination returned a .rar archive - trying a different file combination.', ui_settings.debug)
                                    delete('https://api.real-debrid.com/rest/1.0/torrents/delete/' + torrent_id)
                                    continue
                            if len(release.download) > 0:
                                for link in release.download:
                                    try:
                                        response = post('https://api.real-debrid.com/rest/1.0/unrestrict/link',{'link': link})
                                    except:
                                        break
                                release.files = version.files
                                ui_print(f'[realdebrid] adding cached release:{release.title}|{actual_title}|{torrent_id}')
                                if not actual_title == "":
                                    release.title = actual_title
                                return True
                ui_print('[realdebrid] error: no streamable version could be selected for release: ' + release.title)
                return False
            else:
                try:
                    response = post('https://api.real-debrid.com/rest/1.0/torrents/addMagnet',{'magnet': release.download[0]})
                    time.sleep(0.1)
                    post('https://api.real-debrid.com/rest/1.0/torrents/selectFiles/' + str(response.id),{'files': 'all'})
                    ui_print('[realdebrid] adding uncached release: ' + release.title)
                    return True
                except:
                    continue
        else:
            ui_print('[realdebrid] error: rejecting release: "' + release.title + '" because it doesnt match the allowed deviation', ui_settings.debug)
    return False

# (required) Check Function
def check(element, force=False):
    if force:
        wanted = ['.*']
    else:
        wanted = element.files()
    unwanted = releases.sort.unwanted
    wanted_patterns = list(zip(wanted, [regex.compile(r'(' + key + ')', regex.IGNORECASE) for key in wanted]))
    unwanted_patterns = list(zip(unwanted, [regex.compile(r'(' + key + ')', regex.IGNORECASE) for key in unwanted]))

    hashes = []
    for release in element.Releases[:]:
        if len(release.hash) == 40:
            hashes += [release.hash]
        else:
            ui_print("[realdebrid] error (missing torrent hash): ignoring release '" + release.title + "' ",ui_settings.debug)
            element.Releases.remove(release)
    if len(hashes) > 0:
        response = get('https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/' + '/'.join(hashes))
        ui_print("[realdebrid] checking and sorting all release files ...", ui_settings.debug)
        for release in element.Releases:
            release.files = []
            release_hash = release.hash.lower()
            if hasattr(response, release_hash):
                response_attr = getattr(response, release_hash)
                if hasattr(response_attr, 'rd'):
                    rd_attr = response_attr.rd
                    if len(rd_attr) > 0:
                        for cashed_version in rd_attr:
                            version_files = []
                            for file_ in cashed_version.__dict__:
                                file_attr = getattr(cashed_version, file_)
                                debrid_file = file(file_, file_attr.filename, file_attr.filesize, wanted_patterns, unwanted_patterns)
                                version_files.append(debrid_file)
                            release.files += [version(version_files), ]
                        # select cached version that has the most needed, most wanted, least unwanted files and most files overall
                        release.files.sort(key=lambda x: len(x.files), reverse=True)
                        release.files.sort(key=lambda x: x.wanted, reverse=True)
                        release.files.sort(key=lambda x: x.unwanted, reverse=False)
                        release.wanted = release.files[0].wanted
                        release.unwanted = release.files[0].unwanted
                        release.size = release.files[0].size
                        release.cached += ['RD']
                        continue
        ui_print(f"done Releases: {len(element.Releases)} Cached: {len(release.cached)}",ui_settings.debug)

def user():
    url = "https://api.real-debrid.com/rest/1.0/user"
    response = get(url)
    if response:
        for key, value in vars(response).items():
            ui_print(f"{key}: {value}")


def get_basename(filename):
    basename = os.path.basename(filename)
    name, extension = os.path.splitext(basename)
    if extension in ['.mkv', '.mp4', '.avi']:
        return name
    else:
        return filename

def create_name_dict():
    global name_dict
    
    ui_print("[realdebrid] creating name_dict", debug=ui_settings.debug)
    name_dict = {}
    limit = 2500
    url = f'https://api.real-debrid.com/rest/1.0/torrents?limit={limit}'
    response = get(url, return_generic_response=True)
    ids=set()
    dupe_names={}

    if response:
        total_count = int(response.headers.get('X-Total-Count', 0))
        max_pages = (total_count // limit) + (1 if total_count % limit > 0 else 0)

        data = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
        for torrent in data:
            name = get_basename(torrent.filename)
            if torrent.filename in name_dict:
                dupe_names[torrent.id] = name
            name_dict[name] = torrent
            ids.add(torrent.id)

        for page in range(2, max_pages + 1):  # start from 2 because we already fetched the first page
            url = f'https://api.real-debrid.com/rest/1.0/torrents?page={page}&limit={limit}'
            response = get(url, return_generic_response=True)
            data = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))


            if response:
                for torrent in data:
                    name = get_basename(torrent.filename)
                    if torrent.filename in name_dict:
                        dupe_names[torrent.id] = name
                    name_dict[name] = torrent
                    ids.add(torrent.id)
            else:
                ui_print("[realdebrid] error: Unable to fetch torrents.")
                break  # stop fetching if there's an error

    else:
        ui_print("[realdebrid] error: Unable to fetch torrents.")

    ui_print(f"[realdebrid] Found {len(name_dict)} Titles, {len(ids)} Torrents")
    ui_print(f"[realdebrid] Found {len(dupe_names)} Duplicate Titles")
    #print Titles and ids:
    for n,i in dupe_names.items():
            ui_print(f"[realdebrid] Duplicate Title: {n}: {i}")
            #delete('https://api.real-debrid.com/rest/1.0/torrents/delete/' + n)
    return name_dict

def check_exists(torrent_name):
    name = get_basename(torrent_name)
    if get_basename(name) in name_dict:
        ui_print(f"[realdebrid] Torrent with name {name} exists: {name_dict[name]} Checked {len(name_dict)} names.")
        return True
    else:
        ui_print(f"[realdebrid] Torrent with name {name} does not exist. Checked {len(name_dict)} names.")
        return False


if __name__ == "__main__":
    if not api_key:
        api_key = os.getenv('REALDEBRID_API_KEY')
        print(f'api_key: {api_key}')
    user()
    create_name_dict()
    check = 'Voyeur.2017.1080p.Netflix.WEB-DL.DD5.1.x264-QOQ'
    print(f'check: {check_exists(check)}')
