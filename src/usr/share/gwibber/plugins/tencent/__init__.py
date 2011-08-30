from gwibber.microblog import network, util
from htmlentitydefs import name2codepoint
import re
import gnomekeyring
from oauth import oauth
from gwibber.microblog.util import log, resources
from gettext import lgettext as _
from tencent import key
log.logger.name = "Tencent"

PROTOCOL_INFO = {
  "name": "Tencent",
  "version": "1.0",

  "config": [
    "private:secret_token",
    "access_token",
    "username",
    "color",
    "receive_enabled",
    "send_enabled",
  ],

  "authtype": "oauth1a",
  "color": "#729FCF",

  "features": [
    "send",
    "receive",
    #"search",
    #"tag",
    "reply",
    "responses",
    "private",
    "public",
    "delete",
    #"retweet",
    #"like",
    "send_thread",
    "send_private",
    #"user_messages",
    "sinceid",
    #"lists",
    #"list",
  ],

  "default_streams": [
    "receive",
    "images",
    "responses",
    "private",
    #"lists",
  ],
}

URL_PREFIX = "http://t.qq.com"
API_PREFIX = "http://open.t.qq.com/api"

def unescape(s):
  return re.sub('&(%s);' % '|'.join(name2codepoint),
    lambda m: unichr(name2codepoint[m.group(1)]), s)

class Client:
  def __init__(self, acct):
    self.service = util.getbus("Service")
    if acct.has_key("secret_token") and acct.has_key("password"): acct.pop("password")
    self.account = acct

    if not acct.has_key("access_token") and not acct.has_key("secret_token"):
      return [{"error": {"type": "auth", "account": self.account, "message": _("Failed to find credentials")}}]

    self.sigmethod = oauth.OAuthSignatureMethod_HMAC_SHA1()
    self.consumer = oauth.OAuthConsumer(*key.get_tencent_keys())
    self.token = oauth.OAuthToken(acct["access_token"], acct["secret_token"])

  def _common(self, data):
    m = {};

    try:
      m["mid"] = str(data["id"])
      m["service"] = "tencent"
      m["account"] = self.account["id"]
      if data.has_key("time"):
        m["time"] = data["time"]
      else:
        m["time"] = data["timestamp"]
      if data.has_key("text"):
        m["text"] = unescape(data["text"])
        if data.has_key('source') :
          source = data['source']
          if source and source.has_key("text"):
            m['text'] = m['text'] + '<span class="text" style="padding:5px;margin:5px;border-top:1px solid #ddd;display:inline-block;">' + source['nick'] + ':' + source['text'] + '"</span>'
      else:
        m["text"] = data["text"] = "message has been sent!"
      m["to_me"] = ("@%s" % self.account["username"]) in data["text"]

      m["html"] = m["text"]
      #m["html"] = util.linkify(data["text"],
        #((util.PARSE_HASH, '#<a class="hash" href="%s#search?q=\\1">\\1</a>' % URL_PREFIX),
        #(util.PARSE_NICK, '@<a class="nick" href="%s/\\1">\\1</a>' % URL_PREFIX)), escape=False)

      #m["content"] = util.linkify(data["text"],
        #((util.PARSE_HASH, '#<a class="hash" href="gwibber:/tag?acct=%s&query=\\1">\\1</a>' % m["account"]),
        #(util.PARSE_NICK, '@<a class="nick" href="gwibber:/user?acct=%s&name=\\1">\\1</a>' % m["account"])), escape=False)
      m["content"] = m["text"]

      if data.has_key("retweeted_status"):
        m["retweeted_status"] = data["retweeted_status"]
      else:
        m["retweeted_status"] = None

      if data.has_key('image') and data['image']:
        images = []
        for img in data['image']:
          images.append({"src": img + "/460", "url": img + "/2000"})
          if data.has_key("source") and data['source'] and data['source']['image']:
            for img in data['source']['image']:
              images.append({"src": img + "/460", "url": img + "/2000"})
        if images:
          m["images"] = images
          m["type"] = "photo"
    except:
      log.logger.error("%s common failure - %s", PROTOCOL_INFO["name"], data)
      return {}

    return m

  def _user(self, user):
    return {
        "name": user.get("nick", 'me'),
        "nick": user.get("name",'me'),
        "id": user["id"],
        "location": user.get("location",''),
        "followers": None,
        "image": user.get("head", '') and user.get("head") + '/100',
        "url": "/".join((URL_PREFIX, user.get("name", 'me'))),
        "is_me": user.get("name", 'me') == self.account["username"],
    }

  def _message(self, data):
    if type(data) == type(None):
      return []

    m = self._common(data)
    if data.has_key('from'):
      m["source"] = data['from']
    else:
      m['source'] = 'Gwibber'

    #if data.has_key("in_reply_to_status_id"):
      #if data["in_reply_to_status_id"]:
        #m["reply"] = {}
        #m["reply"]["id"] = data["in_reply_to_status_id"]
        #m["reply"]["nick"] = data["in_reply_to_screen_name"]
        #if m["reply"]["id"] and m["reply"]["nick"]:
          #m["reply"]["url"] = "/".join((URL_PREFIX, m["reply"]["nick"], "statuses", str(m["reply"]["id"])))
        #else:
          #m["reply"]["url"] = None

    m["sender"] = self._user(data)
    m["url"] = "http://t.qq.com/p/t/" + str(m['mid'])
    return m

  def _private(self, data):
    try :
      m = self._message(data)
      m["private"] = True

      m["recipient"] = {}
      m["recipient"]["name"] = data.get("toname", '')
      m["recipient"]["nick"] = data.get("tonick", '')
      m["recipient"]["id"] = data["id"]
      m["recipient"]["image"] = data.get("tohead", '')
      if m["recipient"]['image']:
        m['recipient']['image'] += '/100'
      m["recipient"]["location"] = data["location"]
      m["recipient"]["url"] = "/".join((URL_PREFIX, m["recipient"]["nick"]))
      m["recipient"]["is_me"] = m["recipient"]["nick"] == self.account["username"]
      m["to_me"] = m["recipient"]["is_me"]

      return m
    except Exception as e:
      log.logger.error("%s private failure - %s", PROTOCOL_INFO["name"], data)
      return {}

  def _result(self, data):
    m = self._common(data)

    try :
      if data["to_user_id"]:
        m["reply"] = {}
        m["reply"]["id"] = data["to_user_id"]
        m["reply"]["nick"] = data["to_user"]

      m["sender"] = {}
      m["sender"]["nick"] = data["from_user"]
      m["sender"]["id"] = data["from_user_id"]
      m["sender"]["image"] = data["profile_image_url"]
      m["sender"]["url"] = "/".join((URL_PREFIX, m["sender"]["nick"]))
      m["sender"]["is_me"] = m["sender"]["nick"] == self.account["username"]
      m["url"] = "/".join((m["sender"]["url"], "statuses", str(m["mid"])))
      return m
    except:
      log.logger.error("%s result failure - %s", PROTOCOL_INFO["name"], data)
      return {}

  def _list(self, data):
    try:
      m = {
          "mid": data["id"],
          "service": "tencent",
          "account": self.account["id"],
          "time": 0,
          "text": data["text"],
          "html": data["text"],
          "content": data["text"],
          "url": "/".join((URL_PREFIX, data["name"])),
          "sender": self._user(data),
          "name": data["name"],
          "nick": data["nick"],
          "key": data["nick"],
          "full": data["name"],
          "uri": data["name"],
          "mode": data["type"],
          "members": data["count"],
          "followers": None,
          "kind": "list",
      }
      return m
    except:
      log.logger.error("%s list failure - %s", PROTOCOL_INFO["name"], data)
      return {}

  def _get(self, path, parse="message", post=False, single=False, **args):
    url = "/".join((API_PREFIX, path))

    args['clientip'] = '127.0.0.1'
    args['format'] = 'json'
    request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, self.token,
        http_method=post and "POST" or "GET", http_url=url, parameters=util.compact(args))
    request.sign_request(self.sigmethod, self.consumer, self.token)

    if post:
      data = network.Download(request.to_url(), util.compact(args), post).get_json()
    else:
      data = network.Download(request.to_url(), None, post).get_json()

    resources.dump(self.account["service"], self.account["id"], data)

    if isinstance(data, dict) and data.get("errors", 0):
      if "authenticate" in data["errors"][0]["message"]:
        logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Authentication failed"), error["message"])
        log.logger.error("%s", logstr)
        return [{"error": {"type": "auth", "account": self.account, "message": data["errors"][0]["message"]}}]
      else:
        for error in data["errors"]:
          logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Unknown failure"), error["message"])
          return [{"error": {"type": "unknown", "account": self.account, "message": error["message"]}}]
    elif isinstance(data, dict) and data.get("error", 0):
      if "Incorrect signature" in data["error"]:
        logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Request failed"), data["error"])
        log.logger.error("%s", logstr)
        return [{"error": {"type": "auth", "account": self.account, "message": data["error"]}}]
    elif isinstance(data, str):
      logstr = """%s: %s - %s""" % (PROTOCOL_INFO["name"], _("Request failed"), data)
      log.logger.error("%s", logstr)
      return [{"error": {"type": "request", "account": self.account, "message": data}}]
    if parse == "list":
      return [self._list(l) for l in data["data"]['info']]
    if single: return [getattr(self, "_%s" % parse)(data['data'])]
    if parse: return [getattr(self, "_%s" % parse)(m) for m in data['data']['info']]
    else: return []

  def _search(self, **args):
    return None
    data = network.Download("http://search.twitter.com/search.json", util.compact(args))
    data = data.get_json()["results"]

    return [self._result(m) for m in data]

  def __call__(self, opname, **args):
    return getattr(self, opname)(**args)

  def receive(self, count=util.COUNT, since=None):
    home = self._get("statuses/home_timeline", count=count, since_id=since, type=0)
    mine = self._get("statuses/broadcast_timeline", count=count, since_id=since, type=0)
    return home + mine

  def user_messages(self, id=None, count=util.COUNT, since=None):
    return self._get("statuses/user_timeline", id=id, count=count, since_id=since)

  def responses(self, count=util.COUNT, since=None):
    return self._get("statuses/mentions_timeline", count=count, since_id=since)

  def private(self, count=util.COUNT, since=None):
    private = self._get("private/recv", "private", count=count, since_id=since) or []
    private_sent = self._get("private/send", "private", count=count, since_id=since) or []
    return private + private_sent

  def public(self):
    return self._get("statuses/public_timeline")

  def lists(self, **args):
    following = self._get("%s/lists/subscriptions.json" % self.account["username"], "list") or []
    lists = self._get("%s/lists.json" % self.account["username"], "list") or []
    return following + lists

  def list(self, user, id, count=util.COUNT, since=None):
    return self._get("t/list", per_page=count, since_id=since, ids=id)

  def search(self, query, count=util.COUNT, since=None):
    return self._search(q=query, rpp=count, since_id=since)

  def tag(self, query, count=util.COUNT, since=None):
    return self._search(q="#%s" % query, count=count, since_id=since)

  def delete(self, message):
    return self._get("t/del", None, post=True, do=1, id=message['mid'])

  def like(self, message):
    return self._get("favorites/create/%s.json" % message["mid"], None, post=True, do=1)

  def send(self, message):
    res = self._get("t/add", post=True, single=True,
        content=message)
    return self._get('t/show', post=True, single = True,
        id=res[0]['mid'])

  def send_private(self, message, private):
    self._get("private/add", "private", post=True, single=True,
        content=message, name=private["sender"]["nick"])
    return None

  def send_thread(self, message, target):
    isreply = (message[0] == '@')
    path = 't/re_add'
    if isreply:
      path = 't/comment'
    res = self._get(path, post=True, single=True,
        content=message, reid=target["mid"])
    return self._get('t/show', post=True, single = True,
        id=res[0]['mid'])
