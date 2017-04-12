import random
import time

import requests

from . import logger


class InstaSession(requests.Session):
    url = 'https://www.instagram.com/'
    url_login = 'https://www.instagram.com/accounts/login/ajax/'
    url_logout = 'https://www.instagram.com/accounts/logout/'

    user_agent = ("Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/48.0.2564.103 Safari/537.36")
    accept_language = 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'


    __attrs__ = [
        'headers', 'cookies', 'auth', 'proxies', 'hooks', 'params', 'verify',
        'cert', 'prefetch', 'adapters', 'stream', 'trust_env',
        'max_redirects',
        'url', 'url_login', 'url_logout', 'user_agent', 'accept_langulage',
        'login_status', 'user_id', 'user_login', 'user_password',
    ]

    def __init__(self):
        super(InstaSession, self).__init__()

        self.csrftoken = ''

        self.login_status = False
        self.user_id = None
        self.user_login = None
        self.user_password = None
        self.last_response = None

    def login(self, login=None, password=None):
        if login:
            self.user_login = login.lower()

        if password:
            self.user_password = password

        logger.debug('TRYING TO LOGIN AS: %s' % self.user_login)
        self.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                             'ig_vw': '1920', 'csrftoken': '',
                             's_network': '', 'ds_user_id': ''})

        _login_post = {'username': self.user_login,
                       'password': self.user_password}
        self.headers.update({'Accept-Encoding': 'gzip, deflate',
                             'Accept-Language': self.accept_language,
                             'Connection': 'keep-alive',
                             'Content-Length': '0',
                             'Host': 'www.instagram.com',
                             'Origin': 'https://www.instagram.com',
                             'Referer': self.url,
                             'User-Agent': self.user_agent,
                             'X-Instagram-AJAX': '1',
                             'X-Requested-With': 'XMLHttpRequest'})
        logger.debug('GET %s' % self.url)
        r = self.get(self.url)
        self.headers.update({'X-CSRFToken': r.cookies['csrftoken']})
        time.sleep(5 * random.random())
        logger.debug('POST %s' % self.url_login, extra=_login_post)
        login = self.post(self.url_login, data=_login_post, allow_redirects=True)
        self.last_response = login
        logger.debug('POST STATUS_CODE: %s' % login.status_code)
        self.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        self.csrftoken = login.cookies['csrftoken']
        time.sleep(5 * random.random())

        if login.status_code == 200:
            logger.debug('GET %s' % self.url)
            r = self.get(self.url)
            logger.debug('GET STATUS_CODE: %s' % r.status_code)
            finder = r.text.find(self.user_login)
            if finder != -1:
                self.login_status = True
                logger.debug('LOGIN SUCCESS: %s' % self.user_login)

                return True
            else:
                self.login_status = False
                logger.error('LOGIN ERROR: Check your login data!')
        else:
            logger.error('LOGIN ERROR: Connection error!')

        return False

    def logout(self):
        logger.debug('Logout')

        try:
            logout_post = {'csrfmiddlewaretoken': self.csrftoken}
            logout = self.post(self.url_logout, data=logout_post)
            logger.debug("LOGOUT SUCCESS!")
            self.login_status = False
        except:
            logger.error("LOGOUT ERROR!")
