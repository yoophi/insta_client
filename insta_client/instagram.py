# -*- coding: utf-8 -*-
import json
import re
import urllib
from collections import Counter
from datetime import datetime

from itp import itp
from lxml import html

from . import logger
from .client import InstaWebRateLimitException
from .session import InstaSession


class InstaUserNotFoundError(Exception):
    pass


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
        """
        username 에 해당하는 사용자 찾기

        :param user_id:
        :param username:
        :param session:
        :raises InstaUserNotFoundException: username 에 해당하는 사용자를 찾을 수 없음
        """
        super(InstaUser, self).__init__()

        if not session:
            session = InstaSession()
            session.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                                    'ig_vw': '1920', 'csrftoken': '',
                                    's_network': '', 'ds_user_id': ''})
            session.headers.update({'Accept-Encoding': 'gzip, deflate',
                                    'Accept-Language': self.accept_language,
                                    'Connection': 'keep-alive',
                                    'Content-Length': '0',
                                    'Host': 'www.instagram.com',
                                    'Origin': 'https://www.instagram.com',
                                    'Referer': 'https://www.instagram.com/',
                                    'User-Agent': self.user_agent,
                                    })

        self.s = session
        self.id = user_id
        self.username = username

        self._follows = []
        self._followed_by = []
        self._media = []

        self.follows_count = 1  # FIXME
        self.followed_by_count = 1  # FIXME

        if self.username:
            self.profile_url = 'https://www.instagram.com/{username}/'.format(username=self.username)

            resp = self.s.get(self.profile_url)
            tree = html.fromstring(resp.content)
            _script_text = ''.join(tree.xpath('//script[contains(text(), "sharedData")]/text()'))
            _shared_data = ''.join(re.findall(r'window._sharedData = (.*);', _script_text))

            if resp.status_code == 429:
                raise InstaWebRateLimitException

            if not resp.status_code == 200:
                raise InstaUserNotFoundError

            _data = json.loads(_shared_data)

            try:
                user_obj = _data['entry_data']['ProfilePage'][0]['user']
            except KeyError:
                raise InstaUserNotFoundError

            media_obj = user_obj.pop('media')
            self.info = user_obj
            self.media_count = media_obj['count']
            self.media_page_info = media_obj['page_info']
            for m in media_obj['nodes']:
                self._media.append(self._format_media(m))

            self._last_response = resp
            self._raw = self._data = _data

            self.s.headers.update({'X-CSRFToken': resp.cookies['csrftoken']})

            for key in (
                    'country_block', 'external_url', 'full_name', 'id', 'is_private',
                    'is_verified', 'profile_pic_url', 'biography',
                    'follows_viewer', 'followed_by_viewer',
                    'profile_pic_url_hd', 'username',):
                setattr(self, key, self.info.get(key))

            for key in ('followed_by', 'follows',):
                setattr(self, key + '_count', self.info[key]['count'])

    @property
    def api_data(self):
        return {
            "id": "",
            "username": "",
            "full_name": "",
            "profile_picture": "",
            "bio": "",
            "website": "",
            "counts": {
                "media": "",
                "follows": "",
                "followed_by": ""
            }
        }

    @property
    def avg_comments(self):
        if len(self._media) > 0:
            return sum([m['comments']['count'] for m in self._media]) / len(self._media)

        return 0

    @property
    def avg_likes(self):
        if len(self._media) > 0:
            return sum([m['likes']['count'] for m in self._media]) / len(self._media)

        return 0

    @property
    def last_media_at(self):
        try:
            return datetime.fromtimestamp(self._media[0]['date'])
        except:
            return None

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

    @property
    def gen_followed_by(self):
        """
        generator

        :return:
        """
        idx = 0

        while idx < self.followed_by_count:
            if len(self._followed_by) <= idx:
                if not self._fetch_next_followed_by():
                    break

            try:
                yield self._followed_by[idx]
            except IndexError:
                pass

            idx += 1

    def get_n_followed_by(self, n=10):
        g = self.gen_followed_by
        return [g.next() for _ in range(n)]

    def get_all_followed_by(self):
        return list(self.gen_followed_by)

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

    def _fetch_next_followed_by(self, cnt=10):
        if len(self._followed_by) == 0:
            # first request
            q = """
                ig_user(%s) {
                  followed_by.first(%s) {
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

            self._followed_by_page_info = r1.json()['followed_by']['page_info']
            self.followed_by_count = r1.json()['followed_by']['count']

            nodes = r1.json()['followed_by']['nodes']
            for node in nodes:
                self._followed_by.append(node)

            return len(nodes) > 0

        else:
            if not self._followed_by_page_info['has_next_page']:
                return False

            end_cursor = self._followed_by_page_info['end_cursor']

            q = """
            ig_user(%s) {
              followed_by.after(%s, 10) {
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

            nodes = r2.json()['followed_by']['nodes']
            self._followed_by_page_info = r2.json()['followed_by']['page_info']

            for node in nodes:
                self._followed_by.append(node)

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


class InstaMedia(InstaBase):
    def __init__(self, code=None, session=None):
        super(InstaMedia, self).__init__()

        if not session:
            session = InstaSession()

        self.s = session
        self.url = 'https://www.instagram.com/p/%s/' % (code,)
        self._user = None

        resp = self.s.get(self.url + '?__a=1')
        self._last_response = resp
        self._data = resp.json()['graphql']['shortcode_media']

    @property
    def data(self):
        logger.debug(self._data)

        caption = ''
        try:
            caption = self._data['edge_media_to_caption']['edges'][0]['node']['text']
        except:
            pass

        return {
            'id': self._data['id'],
            'display_src': self._data['display_url'],
            'owner': self._data['owner'],
            'code': self._data['shortcode'],
            'caption': caption,
            'comments_count': self._data['edge_media_to_comment']['count'],
            'likes_count': self._data['edge_media_preview_like']['count'],
        }

    @property
    def id(self):
        return self._data['id']

    @property
    def media_id(self):
        return self._data['id']

    @property
    def insta_id(self):
        return self._data['owner']['id']

    @property
    def code(self):
        return self._data['shortcode']

    @property
    def caption(self):
        try:
            return self._data['edge_media_to_caption']['edges'][0]['node']['text']
        except:
            return ''

    @property
    def display_src(self):
        return self._data['display_url']

    @property
    def comments_count(self):
        return self._data['edge_media_to_comment']['count']

    @property
    def likes_count(self):
        return self._data['edge_media_preview_like']['count']

    @property
    def owner(self):
        return self._data['owner']

    def tags(self):
        return self._parse_caption_hashtags(self.data.get('caption'))

    @property
    def user(self):
        if not self._user:
            if not self.owner['username']:
                raise ValueError('media not loaded')

            self._user = InstaUser(username=self.owner['username'], session=self.s)

        return self._user


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


class InstaFeed(InstaBase):
    def __init__(self, user_id=None, username=None, session=None):
        super(InstaFeed, self).__init__()

        if not session:
            session = InstaSession()
            session.cookies.update({'sessionid': '', 'mid': '', 'ig_pr': '1',
                                    'ig_vw': '1920', 'csrftoken': '',
                                    's_network': '', 'ds_user_id': ''})

            session.headers.update({'Accept-Encoding': 'gzip, deflate',
                                    'Accept-Language': self.accept_language,
                                    'Connection': 'keep-alive',
                                    'Content-Length': '0',
                                    'Host': 'www.instagram.com',
                                    'Origin': 'https://www.instagram.com',
                                    'Referer': 'https://www.instagram.com/',
                                    'User-Agent': self.user_agent,
                                    })

        self.s = session
        self.id = user_id
        self.username = username

        if not self.s.login_status:
            raise Exception('NOT LOGGED IN')

        self.feed_url = 'https://www.instagram.com/'
        resp = self.s.get(self.feed_url)
        tree = html.fromstring(resp.content)
        _script_text = ''.join(
            tree.xpath('//script[contains(text(), "sharedData")]/text()'))
        _shared_data = ''.join(
            re.findall(r'window._sharedData = (.*);', _script_text))

        assert resp.status_code == 200
        data = json.loads(_shared_data)

        feed_media = data['entry_data']['FeedPage'][0]['feed']['media']

        # user_obj = data['entry_data']['ProfilePage'][0]['user']
        # media_obj = user_obj.pop('media')
        # self.info = user_obj
        # self.media_count = media_obj['count']
        # self.media_page_info = media_obj['page_info']
        # for m in media_obj['nodes']:
        #     self._media.append(self._format_media(m))

        media_nodes = feed_media['nodes']
        self.media_page_info = feed_media['page_info']

        for m in media_nodes:
            self._media.append(self._format_media(m))

        self._last_response = resp

        self.s.headers.update({'X-CSRFToken': resp.cookies['csrftoken']})

        # for key in (
        #         'country_block', 'external_url', 'full_name', 'id', 'is_private',
        #         'is_verified', 'profile_pic_url', 'biography',
        #         'profile_pic_url_hd', 'username',):
        #     setattr(self, key, self.info.get(key))
        #
        # for key in ('followed_by', 'follows',):
        #     setattr(self, key + '_count', self.info[key]['count'])

    # def get_n_media(self, n=10):
    #     pass

    @property
    def gen_media(self):
        """
        generator

        :return:
        """
        idx = 0

        while True:
            if len(self._media) <= idx:
                if not self._fetch_next_media():
                    break

            try:
                yield self._media[idx]
            except IndexError:
                pass

            idx += 1

    def _fetch_next_media(self, cnt=33):
        ig_url = 'https://www.instagram.com/query/'
        last_media_id = int(self._media[-1]['id'])

        if not self.media_page_info['has_next_page']:
            raise Exception('NO NEXT PAGE')

        self.s.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
        })

        q = '''
        ig_me() {
          feed {
            media.after(%s, 12) {
              nodes {
                id,
                attribution,
                caption,
                code,
                comments.last(4) {
                  count,
                  nodes {
                    id,
                    created_at,
                    text,
                    user {
                      id,
                      profile_pic_url,
                      username
                    }
                  },
                  page_info
                },
                comments_disabled,
                date,
                dimensions {
                  height,
                  width
                },
                display_src,
                is_video,
                likes {
                  count,
                  nodes {
                    user {
                      id,
                      profile_pic_url,
                      username
                    }
                  },
                  viewer_has_liked
                },
                location {
                  id,
                  has_public_page,
                  name,
                  slug
                },
                owner {
                  id,
                  blocked_by_viewer,
                  followed_by_viewer,
                  full_name,
                  has_blocked_viewer,
                  is_private,
                  profile_pic_url,
                  requested_by_viewer,
                  username
                },
                usertags {
                  nodes {
                    user {
                      username
                    },
                    x,
                    y
                  }
                },
                video_url,
                video_views
              },
              page_info
            }
          },
          id,
          profile_pic_url,
          username
        }
        ''' % (self.media_page_info['end_cursor'],)
        ref = 'feed::show'

        post_data = dict(q=q, ref=ref)

        resp = self.s.post(ig_url, data=post_data, )

        nodes = resp.json()['feed']['media']['nodes']

        self.media_page_info = resp.json()['feed']['media']['page_info']
        self._last_response = resp

        for m in nodes:
            self._media.append(self._format_media(m))

        return len(nodes) > 0


class InstaApiBase(InstaBase):
    def __init__(self, access_token, session=None):
        super(InstaApiBase, self).__init__()
        self.access_token = access_token

        if not session:
            session = InstaSession()

        self.s = session


class InstaApiUser(InstaApiBase):
    pass


class InstaApiMedia(InstaApiBase):
    pass


class InstaApiHashtag(InstaApiBase):
    def __init__(self, hashtag, access_token, session=None):
        super(InstaApiHashtag, self).__init__(access_token, session=session)

        self.hashtag = hashtag

        # 해시태그의 글 갯수 가져오기
        endpoint = 'https://api.instagram.com/v1/tags/%s?access_token=%s' % (hashtag, self.access_token,)
        resp = self.s.get(endpoint)
        self.media_count = resp.json()['data']['media_count']

        # MEDIA 첫 페이지 가져오기
        self.endpoint = 'https://api.instagram.com/v1/tags/%s/media/recent?access_token=%s' % (
        hashtag, self.access_token,)
        resp = self.s.get(self.endpoint)
        self._last_response = resp
        self._pagination = resp.json()['pagination']

        nodes = resp.json()['data']
        for m in nodes:
            self._media.append(self._format_media(m))

    def _format_media(self, media):
        # MEDIA CODE 가져오기
        code = None
        regex = re.compile(
            r'^(?:http)s?://'  # http:// or https://
            r'(?:www.)?'
            r'instagram.com'  # domain...
            r'/p/'  # media ...
            r'([a-zA-Z0-9_-]+)'  # CODE
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        m = regex.match(media['link'])
        if m:
            code = m.group(1)

        media['code'] = code

        return media

    def _fetch_next_media(self):
        resp = self.s.get(self._pagination['next_url'])
        self._last_response = resp
        self._pagination = resp.json()['pagination']

        nodes = resp.json()['data']
        for m in nodes:
            self._media.append(self._format_media(m))

        return len(nodes) > 0
