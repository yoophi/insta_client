import json
import re
import urllib
from collections import Counter

from itp import itp
from lxml import html

from .session import InstaSession


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
        self._followed_by = []

        self.follows_count = 1  # FIXME
        self.followed_by_count = 1  # FIXME

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
                    'is_verified', 'profile_pic_url', 'biography',
                    'profile_pic_url_hd', 'username',):
                setattr(self, key, self.info.get(key))

            for key in ('followed_by', 'follows',):
                setattr(self, key + '_count', self.info[key]['count'])

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

        data = resp.json()
        self.data = data['media']
        for key in self.data.keys():
            setattr(self, key, self.data[key])

        self.tags = self._parse_caption_hashtags(self.data.get('caption'))

    @property
    def user(self):
        if not self._user:
            if not self.owner['username']:
                raise ValueError('media not loaded')

            self._user = InstaUser(username=self.owner['username'])

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