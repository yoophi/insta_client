import datetime

import requests

from . import logger, __version__
from .instagram import InstaUser, InstaMedia, InstaHashtag, InstaFeed
from .session import InstaSession


class InstaLoginRequiredError(Exception):
    pass


class InstaApiClientError(Exception):
    pass


class InstaWebClientError(Exception):
    pass


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

    def _login_required(f):
        def check_login(self, *args, **kwargs):
            if not self.s.login_status:
                raise InstaLoginRequiredError('login required')

            return f(self, *args, **kwargs)

        return check_login

    def __init__(self, login=None, password=None, access_token=None, session=None):
        self.bot_start = datetime.datetime.now()

        if session:
            self.s = session
        else:
            self.s = InstaSession()

        self.api = InstaApiClient(access_token=access_token)

        # convert login to lower
        if login:
            self.user_login = login.lower()

        if password:
            self.user_password = password

        self.media_by_tag = []
        self.csrftoken = ''

        logger.debug('%s v%s started' % (self.__class__.__name__, __version__))

    def login(self, login=None, password=None):
        if login:
            self.user_login = login.lower()

        if password:
            self.user_password = password

        return self.s.login(self.user_login, self.user_password)

    def logout(self):
        return self.s.logout()

    def set_access_token(self, access_token):
        self.api = InstaApiClient(access_token=access_token)

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
        # """
        # TODO: implement
        # """
        # raise NotImplementedError
        username = self.api.get_username_by_id(id)
        return self.get_user_by_username(username)

    def get_user_by_username(self, username):
        return InstaUser(username=username, session=self.s)

    def get_hashtag(self, tagname):
        return InstaHashtag(tagname, session=self.s)

    def get_current_user(self):
        if not self.s.user_login:
            raise InstaWebClientError('not logged in yet')

        return self.get_user(username=self.s.user_login)

    @_login_required
    def get_feed(self):
        return InstaFeed(session=self.s)

    @_login_required
    def comment(self, media_id, text):
        logger.debug('COMMENT: <media_id:%s> <text:%s>' % (media_id, text))
        comment_post = {'comment_text': text}
        url_comment = self.url_comment % media_id
        logger.debug('URL_COMMENT: %s' % url_comment)
        try:
            comment = self.s.post(url_comment, data=comment_post)
            if comment.status_code == 200:
                self.comments_counter += 1
                logger.debug('Write: "%s". #%i.' % (text, self.comments_counter))
            return comment
        except:
            raise InstaWebClientError("EXCEPT on comment!")

    @_login_required
    def like(self, media_id):
        logger.debug('LIKE: <media_id:%s>' % media_id)
        url_likes = self.url_likes % media_id
        try:
            return self.s.post(url_likes)
        except:
            raise InstaWebClientError("EXCEPT on like")

    @_login_required
    def unlike(self, media_id):
        logger.debug('UNLIKE: <media_id:%s>' % media_id)
        url_unlike = self.url_unlike % media_id
        try:
            return self.s.post(url_unlike)
        except:
            raise InstaWebClientError("EXCEPT on unlike")

    @_login_required
    def follow(self, user_id):
        logger.debug('FOLLOW: %s' % user_id)
        url_follow = self.url_follow % user_id
        logger.debug('URL_FOLLOW: %s' % url_follow)
        try:
            follow = self.s.post(url_follow)
            if follow.status_code == 200:
                self.follow_counter += 1
                logger.debug("FOLLOW OK: %s #%i." % (user_id, self.follow_counter))

            return follow
        except Exception as e:
            logger.error("EXCEPT on follow: %s" % e)

    @_login_required
    def unfollow(self, user_id):
        logger.debug('UNFOLLOW: %s' % user_id)
        url_unfollow = self.url_unfollow % user_id
        logger.debug('URL_UNFOLLOW: %s' % url_unfollow)
        try:
            unfollow = self.s.post(url_unfollow)
            if unfollow.status_code == 200:
                logger.debug("UNFOLLOW OK: %s #%i." % (user_id, self.unfollow_counter))

            return unfollow
        except Exception as e:
            logger.error("EXCEPT on unfollow: %s" % e)


class InstaApiClient(object):
    def __init__(self, access_token=None):
        super(InstaApiClient, self).__init__()

        self._access_token = access_token

    @property
    def access_token(self):
        if not self._access_token:
            raise InstaApiClientError('access_token is not found.')

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

    def get_users_self(self):
        url = 'https://api.instagram.com/v1/users/self?access_token=%s' % (self.access_token,)
        rv = requests.get(url)

        try:
            return rv.json()['data']
        except:
            return None
