import datetime

import requests

from . import logger, __version__
from .instagram import InstaUser, InstaMedia, InstaHashtag
from .session import InstaSession


class InstaWebClient(object):
    url = 'https://www.instagram.com/'
    url_tag = 'https://www.instagram.com/explore/tags/'
    url_likes = 'https://www.instagram.com/web/likes/%s/like/'
    url_unlike = 'https://www.instagram.com/web/likes/%s/unlike/'
    url_comment = 'https://www.instagram.com/web/comments/%s/add/'
    url_follow = 'https://www.instagram.com/web/friendships/%s/follow/'
    url_unfollow = 'https://www.instagram.com/web/friendships/%s/unfollow/'
    url_login = 'https://www.instagram.com/accounts/login/ajax/'
    url_logout = 'https://www.instagram.com/accounts/logout/'
    url_media_detail = 'https://www.instagram.com/p/%s/?__a=1'
    url_user_detail = 'https://www.instagram.com/%s/?__a=1'

    user_agent = ("Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/48.0.2564.103 Safari/537.36")
    accept_language = 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'

    # If instagram ban you - query return 400 error.
    error_400 = 0
    # If you have 3 400 error in row - looks like you banned.
    error_400_to_ban = 3
    # If InstaClient think you are banned - going to sleep.
    ban_sleep_time = 2 * 60 * 60

    # All counter.
    like_counter = 0
    follow_counter = 0
    unfollow_counter = 0
    comments_counter = 0

    # List of user_id, that bot follow
    bot_follow_list = []

    # Other.
    user_id = 0
    media_by_tag = 0
    login_status = False

    def __init__(self, login=None, password=None):
        self.bot_start = datetime.datetime.now()

        self.s = InstaSession()

        # convert login to lower
        if login:
            self.user_login = login.lower()

        if password:
            self.user_password = password

        self.media_by_tag = []
        self.csrftoken = ''

        logger.debug('InstaClient v%s started' % __version__)

    def login(self, login=None, password=None):
        if login:
            self.user_login = login.lower()

        if password:
            self.user_password = password

        return self.s.login(self.user_login, self.user_password)

    def logout(self):
        return self.s.logout()

    def get_media(self, code):
        return InstaMedia(code=code, session=self.s)

    def get_user(self, id=None, username=None):
        if id:
            return self.get_user_by_id(id)
        elif username:
            return self.get_user_by_username(username)
        else:
            raise ValueError('Neither id nor username given')

    def get_user_by_id(self, id):
        """
        TODO: implement
        """
        raise NotImplementedError

    def get_user_by_username(self, username):
        return InstaUser(username=username, session=self.s)

    def get_hashtag(self, tagname):
        return InstaHashtag(tagname, session=self.s)


class InstaApiClient(object):
    def __init__(self, access_token=None):
        super(InstaApiClient, self).__init__()

        self._access_token = access_token

    @property
    def access_token(self):
        if not self._access_token:
            raise AttributeError('access_token is not found.')

        return self._access_token

    def get_username_by_id(self, id):
        data = self.get_userdata_by_id(id)

        return data['username']

    def get_userdata_by_id(self, id):
        url = 'https://api.instagram.com/v1/users/%s?access_token=%s' % (id, self.access_token)
        rv = requests.get(url)

        try:
            return rv.json()['data']
        except:
            return None