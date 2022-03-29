import sys
import bs4
import urllib
from pprint import pprint
import requests
import logging
from urllib import parse
import re
import pickle
import os.path
from os import path
import html
from bs4 import BeautifulSoup
# These two lines enable debugging at httplib level (requests->urllib3->http.client)
# You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
# The only thing missing will be the response.body which is not logged.
try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client
#http_client.HTTPConnection.debuglevel = 1

# logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)
#requests_log = logging.getLogger("requests.packages.urllib3")
# requests_log.setLevel(logging.DEBUG)
#requests_log.propagate = True


class Browser():
    def __init__(self, username='', password=''):

        self.current_page = ''
        self.current_response = ''
        self.client = requests.Session()
        if path.exists("cookiejar"):
            try:
                with open('cookiejar', 'rb') as f:
                    self.client.cookies.update(pickle.load(f))
            except EOFError:
                print('cookiejar is empty!')
        self.allow_redirects = True
        self.client.max_redirects = 5
    #    self.client.verify = False
        self.client.strict_mode = True
        self.cookie_jar = ''
        self.last_url = ''
        self.status_code = ''
        self.global_login_data = {'authmethod': 'on',
                                  'userid': username,
                                  'username': username,
                                  'password': password,
                                  'login-form-type': 'pwd',
                                  'chkRememberMe': 'on',
                                  'winauthtype': 'once'}
        self.global_login_url = 'https://oidc.idp.elogin.att.com/pkmslogin.form'

    def request(self, url, data=False):
        self._do_request(url, data)
        if 'www.e-access.att.com' in self.last_url:
            if self._get_cookie(url):
                self._do_request(url, data)
            else:
                return False
        return self.current_page

    def logout(self):
        if path.exists("cookiejar"):
            os.remove("cookiejar")

    def _do_request(self, url, data=False):
        response = ''
        if data:
            response = self.client.post(url, data=data, allow_redirects=True)
        else:
            response = self.client.get(url, allow_redirects=True)

        self.current_page = response.text
        self.current_response = response
        self.last_url = response.url
        with open('cookiejar', 'wb') as f:
            pickle.dump(self.client.cookies, f)

        return self.current_page

    def _get_cookie(self, url):
        if path.exists("cookiejar"):
            os.remove("cookiejar")
        self._do_request(url)
        self._do_request(self.global_login_url, self.global_login_data)
        self._do_request(
            'https://www.e-access.att.com/isam/sps/oidc/rp/ATT-RP/kickoff/ATT-Password?' + url)

        parsed_url = parse.urlsplit(self.last_url)
        try:
            return_url = parse.parse_qs(parsed_url.query)['ReturnURL'].pop()
        except KeyError:
            return False
        self._do_request('https://oidc.idp.elogin.att.com' + return_url)
        regex = r"action=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        action = matches.group(1)
        regex = r"name=\"id_token\" value=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        id_token = matches.group(1)
        regex = r"name=\"state\" value=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        state = matches.group(1)

        data_login = {'id_token': id_token, 'state': state}
        self._do_request(action, data_login)

        regex = r"action=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        action = matches.group(1)

        regex = r"id=\"RelayState\" value=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        relay_state = matches.group(1)

        regex = r"id=\"__VIEWSTATEGENERATOR\" value=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        view_state_generator = matches.group(1)

        regex = r"id=\"__EVENTVALIDATION\" value=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        event_validation = matches.group(1)

        regex = r"id=\"SAMLResponse\" value=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        saml_response = matches.group(1)

        post_data = {'SAMLResponse': saml_response,
                     'RelayState': relay_state,
                     '__VIEWSTATEGENERATOR': view_state_generator,
                     '__EVENTVALIDATION': event_validation}
        self._do_request(action, post_data)
        regex = r"action=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        action = matches.group(1)

        regex = r"name=\"wa\" value=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        wa = matches.group(1)

        regex = r"name=\"wresult\" value=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        wresult = matches.group(1)

        regex = r"name=\"wctx\" value=\"(.*?)\""
        matches = re.search(regex, self.current_page, re.MULTILINE)
        wctx = matches.group(1)

        post_data = {'wa': wa,
                     'wresult': html.unescape(wresult),
                     'wctx': html.unescape(wctx)}

        self._do_request(action, post_data)
        return True


if __name__ == '__main__':
    pass
