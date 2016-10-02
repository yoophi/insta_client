# -*- coding: utf-8 -*-

import datetime
import json
import logging
import random
import re
import time
import urllib
from collections import Counter

import requests
from itp import itp
from lxml import html

__version__ = '0.0.1'

class InstaSession(requests.Session):
    url = 'https://www.instagram.com/'
    url_login = 'https://www.instagram.com/accounts/login/ajax/'
    url_logout = 'https://www.instagram.com/accounts/logout/'

    user_agent = ("Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/48.0.2564.103 Safari/537.36")
    accept_language = 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'

    def __init__(self):
        super(InstaSession, self).__init__()

        self.csrftoken = ''
        self.log_file_path = None
        self.log_mod = 0
        self.login_status = False
        self.user_id = None
        self.user_login = None
        self.user_password = None

    def login(self, login=None, password=None):
        if login:
            self.user_login = login.lower()

        if password:
            self.user_password = password

        log_string = 'Trying to login as %s...\n' % self.user_login
        self.log(log_string)
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
                             'Referer': 'https://www.instagram.com/',
                             'User-Agent': self.user_agent,
                             'X-Instagram-AJAX': '1',
                             'X-Requested-With': 'XMLHttpRequest'})
        r = self.get(self.url)
        self.headers.update({'X-CSRFToken': r.cookies['csrftoken']})
        time.sleep(5 * random.random())
        login = self.post(self.url_login, data=_login_post, allow_redirects=True)
        self.headers.update({'X-CSRFToken': login.cookies['csrftoken']})
        self.csrftoken = login.cookies['csrftoken']
        time.sleep(5 * random.random())

        if login.status_code == 200:
            r = self.get('https://www.instagram.com/')
            finder = r.text.find(self.user_login)
            if finder != -1:
                self.login_status = True
                log_string = '%s login success!' % self.user_login
                self.log(log_string)
            else:
                self.login_status = False
                self.log('Login error! Check your login data!')
        else:
            self.log('Login error! Connection error!')

    def logout(self):
        log_string = 'Logout'
        self.log(log_string)

        try:
            logout_post = {'csrfmiddlewaretoken': self.csrftoken}
            logout = self.post(self.url_logout, data=logout_post)
            self.log("Logout success!")
            self.login_status = False
        except:
            self.log("Logout error!")

    def log(self, log_text):
        """ Write log by print() or logger """

        if self.log_mod == 0:
            try:
                print(log_text)
            except UnicodeEncodeError:
                print("Your text has unicode problem!")
        elif self.log_mod == 1:
            # Create log_file if not exist.
            if self.log_file == 0:
                self.log_file = 1
                now_time = datetime.datetime.now()
                self.log_full_path = '%s%s_%s.log' % (self.log_file_path,
                                                      self.user_login,
                                                      now_time.strftime("%d.%m.%Y_%H:%M"))
                formatter = logging.Formatter('%(asctime)s - %(name)s '
                                              '- %(message)s')
                self.logger = logging.getLogger(self.user_login)
                self.hdrl = logging.FileHandler(self.log_full_path, mode='w')
                self.hdrl.setFormatter(formatter)
                self.logger.setLevel(level=logging.INFO)
                self.logger.addHandler(self.hdrl)

            # Log to log file.
            try:
                self.logger.info(log_text)
            except UnicodeEncodeError:
                print("Your text has unicode problem!")


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

    # Log setting.
    log_file_path = ''
    log_file = 0

    # Other.
    user_id = 0
    media_by_tag = 0
    login_status = False

    def __init__(self, login=None, password=None, log_mod=0, ):

        self.bot_start = datetime.datetime.now()

        self.time_in_day = 24 * 60 * 60

        # log_mod 0 to console, 1 to file
        self.log_mod = log_mod
        # self.s = requests.Session()
        self.s = InstaSession()

        # convert login to lower
        if login:
            self.user_login = login.lower()

        if password:
            self.user_password = password

        self.media_by_tag = []
        self.csrftoken = ''

        now_time = datetime.datetime.now()
        log_string = 'InstaClient v1.0.1 started at %s:\n' % \
                     (now_time.strftime("%d.%m.%Y %H:%M"))
        self.log(log_string)

    def login(self, login=None, password=None):
        if login:
            self.user_login = login.lower()

        if password:
            self.user_password = password

        return self.s.login(self.user_login, self.user_password)

    def logout(self):
        return self.s.logout()

    def log(self, log_text):
        """ Write log by print() or logger """

        if self.log_mod == 0:
            try:
                print(log_text)
            except UnicodeEncodeError:
                print("Your text has unicode problem!")
        elif self.log_mod == 1:
            # Create log_file if not exist.
            if self.log_file == 0:
                self.log_file = 1
                now_time = datetime.datetime.now()
                self.log_full_path = '%s%s_%s.log' % (self.log_file_path,
                                                      self.user_login,
                                                      now_time.strftime("%d.%m.%Y_%H:%M"))
                formatter = logging.Formatter('%(asctime)s - %(name)s '
                                              '- %(message)s')
                self.logger = logging.getLogger(self.user_login)
                self.hdrl = logging.FileHandler(self.log_full_path, mode='w')
                self.hdrl.setFormatter(formatter)
                self.logger.setLevel(level=logging.INFO)
                self.logger.addHandler(self.hdrl)

            # Log to log file.
            try:
                self.logger.info(log_text)
            except UnicodeEncodeError:
                print("Your text has unicode problem!")

    def get_user(self):
        # return InstaUser(username=username, session=self.s)
        pass

    def get_user_by_id(self, id):
        pass

    def get_user_by_username(self, username):
        return InstaUser(username=username, session=self.s)


class InstaBase(object):
    accept_language = 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'
    user_agent = ("Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/48.0.2564.103 Safari/537.36")

    def __init__(self):
        self._media = []
        self.media_count = 0

    def _format_media(self, media):
        media['tags'] = self._parse_caption_hashtags(media.get('caption'))

        return media

    def _parse_caption_hashtags(self, caption):
        if not caption:
            return []

        res = itp.Parser().parse(caption)
        return res.tags

    @property
    def gen_media(self):
        """
        generator

        :return:
        """
        idx = 0

        while idx < self.media_count:
            if len(self._media) <= idx:
                if not self._fetch_next_media():
                    break

            try:
                yield self._media[idx]
            except IndexError:
                pass

            idx += 1

    def get_n_media(self, n=10):
        g = self.gen_media
        return [g.next() for _ in range(n)]

    def get_all_media(self):
        return list(self.gen_media)

    def _fetch_next_media(self):
        raise NotImplementedError

    @property
    def media_tags(self):
        counter = Counter()
        for m in self._media:
            counter += Counter(m['tags'])

        return counter

    @property
    def top_tags(self):
        media_tags = self.media_tags

        return sorted(media_tags.iteritems(), reverse=True, key=lambda m: m[1])


class InstaUser(InstaBase):
    def __init__(self, user_id=None, username=None, session=None):
        super(InstaUser, self).__init__()

        if not session:
            session = InstaSession()

        self.s = session
        self.id = user_id
        self.username = username
        self._follows = []
        self.follows_count = 1  # FIXME

        self.s.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                               'ig_vw': '1920', 'csrftoken': '',
                               's_network': '', 'ds_user_id': ''})

        self.s.headers.update({'Accept-Encoding': 'gzip, deflate',
                               'Accept-Language': self.accept_language,
                               'Connection': 'keep-alive',
                               'Content-Length': '0',
                               'Host': 'www.instagram.com',
                               'Origin': 'https://www.instagram.com',
                               'Referer': 'https://www.instagram.com/',
                               'User-Agent': self.user_agent,
                               })

        if self.username:
            self.profile_url = 'http://instagram.com/{username}'.format(username=self.username)
            resp = self.s.get(self.profile_url)
            tree = html.fromstring(resp.content)
            _script_text = ''.join(
                tree.xpath('//script[contains(text(), "sharedData")]/text()'))
            _shared_data = ''.join(
                re.findall(r'window._sharedData = (.*);', _script_text))

            assert resp.status_code == 200
            data = json.loads(_shared_data)

            user_obj = data['entry_data']['ProfilePage'][0]['user']
            media_obj = user_obj.pop('media')
            self.info = user_obj
            self.media_count = media_obj['count']
            self.media_page_info = media_obj['page_info']
            for m in media_obj['nodes']:
                self._media.append(self._format_media(m))

            self._last_response = resp

            self.s.headers.update({'X-CSRFToken': resp.cookies['csrftoken']})

            for key in (
                    'country_block', 'external_url', 'full_name', 'id', 'is_private',
                    'is_verified', 'profile_pic_url',
                    'profile_pic_url_hd', 'username',):
                setattr(self, key, self.info.get(key))

            for key in ('followed_by', 'follows',):
                setattr(self, key + '_count', self.info[key]['count'])

    @property
    def gen_follows(self):
        """
        generator

        :return:
        """
        idx = 0

        while idx < self.follows_count:
            if len(self._follows) <= idx:
                if not self._fetch_next_follows():
                    break

            try:
                yield self._follows[idx]
            except IndexError:
                pass

            idx += 1

    def get_n_follows(self, n=10):
        g = self.gen_follows
        return [g.next() for _ in range(n)]

    def get_all_follows(self):
        return list(self.gen_follows)

    def _fetch_next_follows(self, cnt=10):
        if len(self._follows) == 0:
            # first request
            q = """
                ig_user(%s) {
                  follows.first(%s) {
                    count,
                    page_info {
                      end_cursor,
                      has_next_page
                    },
                    nodes {
                      id,
                      is_verified,
                      followed_by_viewer,
                      requested_by_viewer,
                      full_name,
                      profile_pic_url,
                      username
                    }
                  }
                }""" % (self.id, cnt)
            ref = 'relationships::follow_list'
            post_data = dict(q=q, ref=ref)

            self.s.headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
            })
            r1 = self.s.post('https://www.instagram.com/query/', data=post_data)

            self._follows_page_info = r1.json()['follows']['page_info']
            self.follows_count = r1.json()['follows']['count']

            nodes = r1.json()['follows']['nodes']
            for node in nodes:
                self._follows.append(node)

            return len(nodes) > 0

        else:
            if not self._follows_page_info['has_next_page']:
                return False

            end_cursor = self._follows_page_info['end_cursor']

            q = """
            ig_user(%s) {
              follows.after(%s, 10) {
                count,
                page_info {
                  end_cursor,
                  has_next_page
                },
                nodes {
                  id,
                  is_verified,
                  followed_by_viewer,
                  requested_by_viewer,
                  full_name,
                  profile_pic_url,
                  username
                }
              }
            }""" % (self.id, end_cursor)
            ref = 'relationships::follow_list'
            post_data = dict(q=q, ref=ref)

            self.s.headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
            })
            r2 = self.s.post('https://www.instagram.com/query/', data=post_data)

            assert r2.status_code == 200

            nodes = r2.json()['follows']['nodes']
            self._follows_page_info = r2.json()['follows']['page_info']

            for node in nodes:
                self._follows.append(node)

            return len(nodes) > 0

    def _fetch_next_media(self, cnt=33):
        ig_url = 'https://www.instagram.com/query/'
        last_media_id = int(self._media[-1]['id'])

        self.s.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
        })

        q = '''ig_user(%s) { media.after(%s, %d) {
          count,
          nodes {
            caption,
            code,
            comments {
              count
            },
            comments_disabled,
            date,
            dimensions {
              height,
              width
            },
            display_src,
            id,
            is_video,
            likes {
              count
            },
            owner {
              id
            },
            thumbnail_src,
            video_views
          },
          page_info
          }
        }''' % (self.id, last_media_id, cnt)
        ref = 'users::show'
        post_data = dict(q=q, ref=ref)

        resp = self.s.post(ig_url, data=post_data, )
        nodes = resp.json()['media']['nodes']

        self.media_page_info = resp.json()['media']['page_info']
        self._last_response = resp

        for m in nodes:
            self._media.append(self._format_media(m))

        return len(nodes) > 0


class InstaMedia(object):
    pass


class InstaHashtag(InstaBase):
    def __init__(self, tagname, session=None):
        super(InstaHashtag, self).__init__()

        self.hashtag_url = 'https://www.instagram.com/explore/tags/%s/?__a=1' % tagname
        if not session:
            session = InstaSession()

        self.s = session

        resp = self.s.get(self.hashtag_url)
        data = resp.json()['tag']

        self._last_response = resp
        self.s.headers.update({'X-CSRFToken': resp.cookies['csrftoken']})

        # set data
        self.name = data['name']
        self.top_posts = data['top_posts']['nodes']

        # self.__media = data['media']
        self.media_count = data['media']['count']
        self.media_page_info = data['media']['page_info']

        for m in data['media']['nodes']:
            self._media.append(self._format_media(m))

    def _fetch_next_media(self, cnt=7):
        quoted_tag = urllib.quote(str(self.name))

        try:
            end_cursor = self._last_response.json()['tag']['media']['page_info']['end_cursor']
        except KeyError:
            end_cursor = self._last_response.json()['media']['page_info']['end_cursor']

        q = '''
            ig_hashtag(%s) { media.after(%s, %d) {
                count,
                nodes {
                  caption,
                  code,
                  comments {
                    count
                  },
                  comments_disabled,
                  date,
                  dimensions {
                    height,
                    width
                  },
                  display_src,
                  id,
                  is_video,
                  likes {
                    count
                  },
                  owner {
                    id
                  },
                  thumbnail_src,
                  video_views
                },
                page_info
              }
            }''' % (self.name, end_cursor, cnt)
        ref = 'tags::show'
        post_data = dict(q=q, ref=ref)
        url = 'https://www.instagram.com/query/'

        self.s.headers.update({
            'X-CSRFToken': (self._last_response.cookies['csrftoken']),
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://www.instagram.com/explore/tags/' + quoted_tag + '/'
        })
        resp = self.s.post(url, data=post_data)
        nodes = resp.json()['media']['nodes']

        self._last_response = resp

        for m in nodes:
            self._media.append(self._format_media(m))

        return len(nodes) > 0


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
