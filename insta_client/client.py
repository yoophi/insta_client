# -*- coding: utf-8 -*-
from datetime import datetime

import requests
from simplejson import JSONDecodeError

from . import logger, __version__
from .instagram import InstaUser, InstaMedia, InstaApiHashtag, InstaHashtag, InstaFeed
from .session import InstaSession


class InstaLoginRequiredError(Exception):
    pass


class InstaApiClientError(Exception):
    pass


class InstaWebClientError(Exception):
    pass


class BadRequestException(Exception):
    pass


class InvalidAccessTokenException(Exception):
    pass


class NotFoundException(Exception):
    pass


class RateLimitException(Exception):
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
    accept_language = 'ko-KR,ko;q=0.8,en-US;q=0.6,en;q=0.4'

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

    def _check_ratelimit(key):
        def check_ratelimit(f):
            def func(self, *args, **kwargs):
                if self.ratelimit_enabled(key):
                    ratelimit_key = self.get_ratelimit_key(key)
                    if self.cache.get(ratelimit_key) > getattr(self, '%s_per_hour' % key):
                        raise RateLimitException(key)

                return f(self, *args, **kwargs)

            return func

        return check_ratelimit

    def get_ratelimit(self, key=None):
        if not self.cache:
            return

        if key:
            return self.cache.get(self.get_ratelimit_key(key))

        return {
            key: self.cache.get(self.get_ratelimit_key(key))
            for key in ('comment', 'like', 'follow')
        }

    def ratelimit_enabled(self, key):
        return self.cache and getattr(self, '%s_per_hour' % key)

    def get_ratelimit_key(self, key):
        return 'IWC:RATELIMIT:%s:%s:%s' % (self.user_login, key, datetime.now().strptime('%Y%m%d:%H'))

    def inc_ratelimit(self, key):
        if not self.cache:
            return

        ratelimit_key = self.get_ratelimit_key(key)
        logger.debug('ratelimit_key %s' % ratelimit_key)
        self.cache.cache.inc(ratelimit_key)

        rv = self.cache.get(ratelimit_key)
        if rv:
            rv = self.cache.cache.inc(ratelimit_key)
        else:
            self.cache.set(ratelimit_key, 1, timeout=3600)
            rv = 1

        return rv

    def __init__(self, login=None, password=None, access_token=None, session=None,
                 follow_per_hour=None, like_per_hour=None, comment_per_hour=None, cache=None,):
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

        self.cache = cache  # Flask-Cache RedisCache instance
        self.comment_per_hour = comment_per_hour
        self.follow_per_hour = follow_per_hour
        self.like_per_hour = like_per_hour

        self.last_response = None

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

    @_login_required
    def get_current_user(self):
        return self.get_user(username=self.s.user_login)

    def check_login_status(self):
        resp = self.s.get('https://www.instagram.com/')
        self.last_response = resp

        for s in resp.text.split('\n')[:5]:
            if s.find('not-logged-in') >= 0:
                return False

        return True

    @_login_required
    def get_feed(self):
        return InstaFeed(session=self.s)

    @_login_required
    @_check_ratelimit('comment')
    def comment(self, media_id, text):
        logger.debug('COMMENT: <media_id:%s> <text:%s>' % (media_id, text))
        comment_post = {'comment_text': text}
        url_comment = self.url_comment % media_id
        logger.debug('URL_COMMENT: %s' % url_comment)

        resp = self.s.post(url_comment, data=comment_post)
        self.last_response = resp

        try:
            if resp.json().get('status') == 'ok':
                if self.ratelimit_enabled('comment'):
                    self.inc_ratelimit('comment')

                self.comments_counter += 1
                logger.debug('Write: "%s". #%i.' % (text, self.comments_counter))
                return True

        except JSONDecodeError:
            if resp.text.find('not-logged-in') >= 0:
                raise InstaLoginRequiredError

        except:
            raise InstaWebClientError("EXCEPT on comment!")

    @_login_required
    @_check_ratelimit('like')
    def like(self, media_id):
        logger.debug('LIKE: <media_id:%s>' % media_id)
        url_likes = self.url_likes % media_id

        resp = self.s.post(url_likes)
        self.last_response = resp

        try:
            if resp.json().get('status') == 'ok':
                if self.ratelimit_enabled('like'):
                    self.inc_ratelimit('like')

                return True

        except JSONDecodeError:
            if resp.text.find('not-logged-in') >= 0:
                raise InstaLoginRequiredError

        except:
            raise InstaWebClientError("EXCEPT on like")

    @_login_required
    @_check_ratelimit('like')
    def unlike(self, media_id):
        logger.debug('UNLIKE: <media_id:%s>' % media_id)
        url_unlike = self.url_unlike % media_id

        resp = self.s.post(url_unlike)
        self.last_response = resp

        try:
            if resp.json().get('status') == 'ok':
                if self.ratelimit_enabled('like'):
                    self.inc_ratelimit('like')

                return True

        except JSONDecodeError:
            if resp.text.find('not-logged-in') >= 0:
                raise InstaLoginRequiredError

        except:
            raise InstaWebClientError("EXCEPT on unlike")

    @_login_required
    def user_followed_user(self, username):
        u = self.get_user_by_username(username)
        if u.followed_by_viewer:
            return True

        return False

    @_login_required
    @_check_ratelimit('follow')
    def follow(self, user_id):
        logger.debug('FOLLOW: %s' % user_id)
        url_follow = self.url_follow % user_id
        logger.debug('URL_FOLLOW: %s' % url_follow)

        resp = self.s.post(url_follow)
        self.last_response = resp

        try:
            if resp.json().get('status') == 'ok':
                if self.ratelimit_enabled('follow'):
                    self.inc_ratelimit('follow')

                self.follow_counter += 1
                logger.debug("FOLLOW OK: %s #%i." % (user_id, self.follow_counter))
                return True

        except JSONDecodeError:
            if resp.text.find('not-logged-in') >= 0:
                raise InstaLoginRequiredError

        except Exception as e:
            logger.error("EXCEPT on follow: %s %s" % (type(e), str(e)))
            raise InstaWebClientError("EXCEPT on follow: %s" % e)

    @_login_required
    @_check_ratelimit('follow')
    def unfollow(self, user_id):
        logger.debug('UNFOLLOW: %s' % user_id)
        url_unfollow = self.url_unfollow % user_id
        logger.debug('URL_UNFOLLOW: %s' % url_unfollow)

        resp = self.s.post(url_unfollow)
        self.last_response = resp

        try:
            if resp.json().get('status') == 'ok':
                if self.ratelimit_enabled('follow'):
                    self.inc_ratelimit('follow')

                logger.debug("UNFOLLOW OK: %s #%i." % (user_id, self.unfollow_counter))
                return True

        except JSONDecodeError:
            if resp.text.find('not-logged-in') >= 0:
                raise InstaLoginRequiredError

        except Exception as e:
            logger.error("EXCEPT on unfollow: %s" % e)
            raise InstaWebClientError("EXCEPT on unfollow: %s" % e)

    def serialize(self):
        if not self.s:
            raise Exception('Not logged in')

        return {
            'csrftoken': self.csrftoken,
            's.login_status': self.s.login_status,
            's.user_login': self.s.user_login,
            's.user_password': self.s.user_password,
            's.headers': dict(self.s.headers),
            's.cookies': self.s.cookies.get_dict(),
        }

    def deserialize(self, data):
        if not self.s:
            self.s = requests.Session()

        self.csrftoken = data.get('csrftoken')

        for k in ['login_status', 'user_login', 'user_password',]:
            setattr(self.s, k, data.get('s.%s' % k))

        for k, v in data.get('s.cookies').items():
            self.s.cookies.set(k, v)

        self.s.headers.update(data.get('s.headers', {}))


class InstaApiClient(object):
    def __init__(self, access_token=None):
        super(InstaApiClient, self).__init__()

        self._access_token = access_token
        self.last_response = None

    def validate_response(self, resp, msg):
        ratelimit = resp.headers.get('x-ratelimit-remaining')
        logger.debug('RATELIMIT: %s / %s' % (ratelimit, msg))

        if resp.status_code == 200:
            return True

        logger.debug(resp.text)

        if resp.status_code == 400:
            try:
                error_type = resp.json()['meta']['error_type']
            except Exception as e:
                print type(e), str(e)

            if error_type == 'OAuthAccessTokenException':
                raise InvalidAccessTokenException(msg)
            elif error_type == 'APINotFoundError':
                raise NotFoundException(msg)

            raise BadRequestException(msg)
        elif resp.status_code == 429:
            raise RateLimitException(msg)

    @property
    def access_token(self):
        if not self._access_token:
            raise InstaApiClientError('access_token is not found.')

        return self._access_token

    def get_user_follows(self, next_page_url=None):
        url = 'https://api.instagram.com/v1/users/self/follows?access_token=%s' % (self.access_token,)

        if next_page_url:
            url = next_page_url

        rv = requests.get(url)

        self.last_response = rv
        self.validate_response(rv, 'GET /users/self/follows')

        next_url = None
        data = rv.json().get('data', [])
        try:
            next_url = rv.json()['pagination']['next_url']
        except:
            pass

        return data, next_url is not None, next_url

    def get_user_followed_by(self, next_page_url=None):
        url = 'https://api.instagram.com/v1/users/self/followed-by?access_token=%s' % (self.access_token,)

        if next_page_url:
            url = next_page_url

        rv = requests.get(url)

        self.last_response = rv
        self.validate_response(rv, 'GET /users/self/followed-by')

        next_url = None
        data = rv.json().get('data', [])
        try:
            next_url = rv.json()['pagination']['next_url']
        except:
            pass

        return data, next_url is not None, next_url

    def get_username_by_id(self, id):
        data = self.get_userdata_by_id(id)

        return data['username']

    def get_userdata_by_id(self, id):
        url = 'https://api.instagram.com/v1/users/%s?access_token=%s' % (id, self.access_token)
        rv = requests.get(url)

        self.last_response = rv
        self.validate_response(rv, 'GET /users/%s' % id)

        try:
            return rv.json()['data']
        except:
            return None

    def get_users_self(self):
        url = 'https://api.instagram.com/v1/users/self?access_token=%s' % (self.access_token,)
        rv = requests.get(url)

        self.last_response = rv
        self.validate_response(rv, 'GET /users/self')

        try:
            return rv.json()['data']
        except:
            return None

    def like_media(self, media_id):
        url = 'https://api.instagram.com/v1/media/%s/likes?access_token=%s' % (media_id, self.access_token)
        rv = requests.post(url, {})

        self.last_response = rv
        self.validate_response(rv, 'POST /media/%s/likes' % media_id)

        return rv

    def unlike_media(self, media_id):
        url = 'https://api.instagram.com/v1/media/%s/likes?access_token=%s' % (media_id, self.access_token)
        rv = requests.delete(url)

        self.last_response = rv
        self.validate_response(rv, 'DELETE /media/%s/likes' % media_id)

        return rv

    def follow_user(self, user_id):
        url = 'https://api.instagram.com/v1/users/%s/relationship?access_token=%s' % (user_id, self.access_token,)
        rv = requests.post(url, {'action': 'follow'})

        self.last_response = rv
        self.validate_response(rv, 'POST users/%s/relationship' % user_id)

        return rv

    def unfollow_user(self, user_id):
        url = 'https://api.instagram.com/v1/users/%s/relationship?access_token=%s' % (user_id, self.access_token,)
        rv = requests.post(url, {'action': 'unfollow'})

        self.last_response = rv
        self.validate_response(rv, 'POST users/%s/relationship' % user_id)

        return rv

    def get_media(self, media_id):
        url = 'https://api.instagram.com/v1/media/%s?access_token=%s' % (media_id, self.access_token,)
        rv = requests.get(url)

        self.last_response = rv
        self.validate_response(rv, 'GET /media/%s' % (media_id,))

        return rv.json()['data']

    def user_followed_user(self, user_id):
        url = 'https://api.instagram.com/v1/users/%s/relationship?access_token=%s' % (user_id, self.access_token,)
        rv = requests.get(url)

        self.last_response = rv
        self.validate_response(rv, 'GET /users/%s/relationship' % (user_id,))

        try:
            return rv.json()['data']['outgoing_status'] == 'follows'
        except Exception:
            pass

        return False

    def user_liked_media(self, media_id):
        media = self.get_media(media_id)

        try:
            return media.get('user_has_liked')
        except Exception:
            pass

        return False

    def user_recent_media(self, user_id):
        url = 'https://api.instagram.com/v1/users/%s/media/recent?access_token=%s' % (user_id, self.access_token,)
        rv = requests.get(url)

        self.last_response = rv
        self.validate_response(rv, 'GET /users/%s/media/recent' % (user_id,))

        return rv.json()['data']

    def self_recent_media(self):
        return self.user_recent_media('self')

    def media_likes(self, media_id):
        url = 'https://api.instagram.com/v1/media/%s/likes?access_token=%s' % (media_id, self.access_token,)
        rv = requests.get(url)

        self.last_response = rv
        self.validate_response(rv, 'GET /media/%s/likes' % (media_id,))

        return rv.json()['data']

    def get_tag_recent_media(self, hashtag):
        url = 'https://api.instagram.com/v1/tags/%s/media/recent?access_token=%s' % (hashtag, self.access_token,)
        rv = requests.get(url)

        self.last_response = rv
        self.validate_response(rv, 'GET /tags/%s/media/recent' % (hashtag,))

        return rv.json()['data']

    def get_hashtag(self, hashtag):
        return InstaApiHashtag(hashtag, self.access_token)
