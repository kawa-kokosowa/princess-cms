"""The HTML form for managing a blog post.

I could make a decorator for adding the cursor keyword argument to
override the...

"""

import sqlite3 as sqlite
from pcms import doc
from cStringIO import StringIO
import math
import base64
import hashlib
import os
import Cookie
import cgi
import uuid


NO_RESULTS = '<p>No results for query: <em>%s</em>.</p>'
LIST_TITLE = '<h1 id="list-title">%s</h1>'
TAG_LIST_ITEM = '<li><a href="/index.py?list=1&tag=%s">%s</a></li>'
TAG_LIST_CONTAINER = '<ul class="tags">%s</ul>'
ARCHIVE_TITLE = '<h1 id="list-title">Archive</h1>'
ARCHIVE_TITLEBAR = 'Archive'
PERMALINK = '/index.py?view=%s'
NO_ARTICLES_YET = """
                  <p>
                  No articles, yet! You could
                  <a href="/index.py?new=1">create a new article&hellip;</a>
                  </p>
                  """

# derp
LOGIN_FORM = """\
<form method="POST" action="/index.py">
  <input type="text" name="username">
  <input type="password" name="password">
<input type="submit" value="login" name="login">
</form>
"""


def install(install, username=None, password=None, comment=None, email=None):

    if install != 'yes':

        return doc.include('blog', 'install_form.html')[0]

    # reset database
    connection, cursor = connect()
    sql = '''
          DROP TABLE IF EXISTS article;
          DROP TABLE IF EXISTS tag;
          DROP TABLE IF EXISTS article_tag;
          DROP TABLE IF EXISTS user;
          DROP TABLE IF EXISTS role;
          DROP TABLE IF EXISTS permission;
          DROP TABLE IF EXISTS role_permission;
          DROP TABLE IF EXISTS login_attempt;
          DROP TABLE IF EXISTS session;

          CREATE TABLE article (
            article_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created TEXT DEFAULT CURRENT_TIMESTAMP,
            modified TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            author INTEGER NOT NULL
          );

          CREATE TABLE tag (
            tag_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
          );

          CREATE TABLE article_tag (
            article_id INTEGER REFERENCES article(article_id),
            tag_id INTEGER REFERENCES tag(tag_id),

            PRIMARY KEY (article_id, tag_id) ON CONFLICT IGNORE
          );

          CREATE TABLE user (
            user_id INTEGER PRIMARY KEY,
            role_id INTEGER REFERENCES role(role_id),
            username TEXT NOT NULL UNIQUE,
            digest TEXT NOT NULL,
            salt TEXT NOT NULL,
            email TEXT UNIQUE,
            comment TEXT
          );

          CREATE TABLE permission (
            permission_id INTEGER PRIMARY KEY,
            label TEXT UNIQUE
          );

          CREATE TABLE role_permission (
            role_id INTEGER PRIMARY KEY,
            permission_id INTEGER REFERENCES permission(permission_id) NOT NULL
          );

          CREATE TABLE role (
            role_id INTEGER PRIMARY KEY,
            label TEXT NOT NULL UNIQUE
          );

          CREATE TABLE login_attempt (
            user_id INTEGER REFERENCES user(user_id),
            ip TEXT,
            error INTEGER,
            time TEXT DEFAULT CURRENT_TIMESTAMP
          );

          CREATE TABLE session (
            session_id TEXT UNIQUE,
            user_id REFERENCES user(user_id)
          );
          '''
    cursor.executescript(sql)
    connection.commit()

    # create admin role and add new user, assigning to said admin role
    # create the administrator role...
    cursor.execute('INSERT INTO role (label) VALUES (?)', ('administrator',))
    role_id = cursor.lastrowid

    # ... skip permissions for now.
    connection.commit()
    connection.close()

    # create a new session, user, and print user page
    user_config = {
                   'role_id': role_id,
                   'password': password,
                   'email': email,
                   'comment': comment,
                  }
    user = User(username, **user_config)
    session = Session(username).new()

    return str(user)


def user_login_attempt(username, error=0):
    ip = cgi.escape(os.environ['REMOTE_ADDR'])
    user_id = User(username)['user_id']

    connection, cursor = connect()
    sql = 'INSERT INTO login_attempt (user_id, ip, error) VALUES (?, ?, ?)'
    params = (user_id, ip, error)
    cursor.execute(sql, params)
    connection.commit()
    connection.close()

    return None


class User(MasterTable):
    """Read-only user information from the user table..."""

    def __init__(self, username=None, row_id=None, **kwargs):

        # get the row id from the username
        if username and row_id is None:
            connection, cursor = connect()
            sql = 'SELECT id FROM user WHERE username=?'
            cursor.execute(sql, (username,))
            row_id = cursor.fetchone()['row_id']
            connection.close()

        self.row_id = row_id

        # we're creating the user
        if kwargs:
            # sanitize the username first
            allowed = ('-', '_')
            username = username.strip()
            t = '-'.join(username.split())  # divide words with dashes
            u = ''.join([c for c in t if c.isalnum() or c in allowed])
            clean_username = u[:20].rstrip('-').lower()

            # user's parameters
            role_id = kwargs['role_id']
            password = kwargs['password']
            email = kwargs['email']
            comment = kwargs['comment']
            digest, salt = user_password_hash(password)

            # finally insert parameters into db
            connection, cursor = connect()
            sql = '''
                  INSERT INTO user (
                    role_id,
                    username,
                    digest,
                    salt,
                    email,
                    comment
                  )

                  VALUES (?, ?, ?, ?, ?, ?)
                  '''
            params = (role_id, username, digest, salt, email, comment)
            cursor.execute(sql, params)
            connection.commit()
            connection.close()

    def row(self):
        """Fetch user's data..."""

        connection, cursor = connect()
        cursor.execute('SELECT * FROM user WHERE id=?', (self.row_id,))
        row = cursor.fetchone()
        connection.close()

        return row

    def __getitem__(self, key):

        return self.row().get(key, None)

    def is_password(self, attempt):
        digest = self['digest']
        salt = self['salt']
        success = user_password_hash(attempt, salt)[0] == digest

        if success:
            user_login_attempt(self.username)

            return True

        else:
            user_login_attempt(self.username, 1)

            return False

    def __str__(self):
        definition_list = (
                           '<dl class="user-info">'
                           '  <dt>User ID</dt>'
                           '  <dd>%(user_id)s</dd>'
                           '  <dt>Username</dt>'
                           '  <dd>%(username)s</dd>'
                           '  <dt>Digest</dt>'
                           '  <dd>%(digest)s</dd>'
                           '  <dt>Salt</dt>'
                           '  <dd>%(salt)s</dd>'
                           '  <dt>Email</dt>'
                           '  <dd>%(email)s</dd>'
                           '  <dt>Comment</dd>'
                           '  <dd>%(comment)s</dd>'
                           '</dl>'
                           % self.row()
                          )

        return definition_list


class Session(object):
    """Manage database, cookie, for login sessions
    
    Store user ID in cookie? Negate username?
    
    """

    def __init__(self, username=None):

        if username:
            self.username = username
            self.user_id = User(username)['user_id']

    def __str__(self):
        """Return the session ID"""

        connection, cursor = connect()
        sql = 'SELECT session_id FROM session WHERE user_id=?'
        cursor.execute(sql, (self.user_id,))
        session_id = cursor.fetchone()['session_id']
        connection.close()

        return session_id

    def __nonzero__(self):
        # read cookie session id first
        cookie_string = os.environ.get('HTTP_COOKIE')

        if os.environ.get('HTTP_COOKIE') == '':

            return False

        cookie = Cookie.SimpleCookie()
        cookie.load(cookie_string)
        cookie_val = cookie['session_id'].value

        # compare session table's session id for user, against cookie's
        return cookie['session_id'].value == str(self)

    def new(self):
        """Associates a new session ID with the username.

        Creates a cookie to store said session ID, and creates the
        corresponding entry in the session table.

        You cannot check a session on the same page which sets the
        cookie. The database will yield None.

        """

        session_id = base64.b64encode(os.urandom(128))
        cookie = Cookie.SimpleCookie()
        cookie['session_id'] = session_id
        print cookie

        connection, cursor = connect()
        sql = '''
              INSERT OR REPLACE INTO session (session_id, user_id)
              VALUES (?, ?)
              '''
        cursor.execute(sql, (session_id, self.user_id))
        connection.commit()
        connection.close()

    def delete(self):
        """Typically accessed as "logout."

        Deletes the session id associated with the username from the
        session table.

        """

        connection, cursor = connect()
        cursor.execute('DELETE from session WHERE user_id=?', (self.user_id,))
        connection.commit()
        connection.close()


def connect():
    """We have some generic database initialization configurations."""

    def dict_factory(cursor, row):
        """Typical sqlite row-to-dictionary patch."""
        d = {}

        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]

        return d

    connection = sqlite.connect('pcms/blog/blog.db')
    connection.row_factory = dict_factory
    cursor = connection.cursor()

    return connection, cursor


def user_update(username, password):
    user_id = user_id or '1'
    user_id = int(user_id)


def user_password_hash(password, salt=None):
    """Return hash for password.

    Primarily for user account passwords.

    """

    if salt is None:
        salt = uuid.uuid4().hex

    digest = hashlib.sha256(password + salt).hexdigest()

    for x in xrange(0, 100001):
        digest = hashlib.sha256(digest).hexdigest()

    return digest, salt


def user_login(username=None, password=None, check_session=True):
    """Give login success page (profile/user info page), or login
    failure page.

    This is the primary "mapping" for all user login/logout
    interactions. It provides the login form, and success/error
    pages.

    Args:
      username (str)
      password (str)

    Returns:
      str: a message depicting the status of the login.

    Notes:
      install only sends username, password

    """


    # check for cookie first... (if session...)
    user = User(username)
    session = Session(username)

    if check_session and session:

        return str(user)

    # serve the login form
    if username is None and password is None:

        return LOGIN_FORM

    # return message about username or password field being left
    # blank
    elif not all([username, password]):

        return '<p>Missing field...</p>' + LOGIN_FORM

    # the password is incorrect
    if not user.is_password(password):
        return '<p>Username/password combination incorrect.</p>' + LOGIN_FORM

    # create new session and store success in log; test session with
    # user info page
    session.new()

    return str(user)


def user_new(username=None, password=None, email=None, comment=None):
    """Create a NEW user and build their row in the user table.

    Returns:
      str: HTML representation of user's row in user table.

    Raises:
      sqlite.IntegrityError: duplicate username!

    """

    user_params = {'username': username, 'password': password, 'email': email,
                   'comment': comment}
    user = User(username, **user_params)
    return str(User(username))


class MasterTable(object):
    """Define on init:

    self.table
    self.row_id

    """

    def __getitem__(self, key):
        return self.row()[key]

    def __setitem__(self, key, value):
        connection, cursor = connect()
        sql = 'UPDATE %s SET %s=? WHERE id=?' % (self.table, key)
        params = (value, self.row_id)
        cursor.execute(sql, params)
        connection.commit()
        connection.close()

    def row(self):
        connection, cursor = connect()
        cursor.execute('SELECT * FROM %s WHERE id=?', (self.row_id,))
        row = cursor.fetchone()
        connection.close()

        return row

    def delete_master(self):
        connection, cursor = connect()
        params = (self.row_id,)
        sql = 'DELETE FROM %s WHERE id=?' % self.table
        cursor.execute(sql, params)
        connection.commit()
        connection.close()

        return None


class Article(MasterTable):
    """Abstraction for a blog or page article.

    """

    def __init__(self, article_id, **kwargs):
        """If kwargs, create or save.

        Args:
          article_id (int): ...
          **kwargs: ...

        """

        self.row_id = article_id

        # either create or update the article
        if kwargs:
            connection, cursor = connect()

            try:
                sql = '''
                      INSERT INTO article (article_id, title, body)
                      VALUES (?, ?, ?)
                      '''
                params = (article_id, kwargs['title'], kwargs['body'])
                cursor.execute(sql, params)

            except sqlite.IntegrityError:
                sql = '''
                      UPDATE article SET
                      title=?,
                      body=?
                      WHERE article_id=?
                      '''
                params = (kwargs['title'], kwargs['body'], article_id)
                cursor.execute(sql, params)

            tags = doc.strip_html(tags.strip())

            # disassociate previous tags from article, first!
            sql = 'DELETE FROM article_tag WHERE article_id=?'
            cursor.execute(sql, (article_id,))

            # make sure tag exists
            tags = kwargs['tags'].split(',')
            sql = 'INSERT OR IGNORE INTO tag (name) VALUES (?)'
            cursor.executemany(sql, [(tag,) for tag in tags])

            # link tags to article
            params = zip([article_id] * len(tags), tags)
            sql = '''
                  INSERT INTO article_tag (article_id, tag_id)
                  SELECT ?, tag_id FROM tag WHERE name=?
                  '''
            cursor.executemany(sql, params)

            # finished!
            connection.commit()
            connection.close()

    def delete_all(self):
        self.delete_master()
        connection, cursor = connect()
        params = (self.row_id,)
        cursor.execute('DELETE FROM article_tag WHERE article_id=?', params)
        connection.commit()

        return None

    def get_tags_str(self, make_links=False):
        connection, cursor = connect()
        sql = '''
              SELECT tag.name FROM article_tag
              NATURAL JOIN tag
              NATURAL JOIN article
              WHERE article_id=?
              '''
        cursor.execute(sql, (article_id,))
        tags = cursor.fetchall()
        connection.close()

        if link:
            # need to make urlsafe first... I'm not doing that now
            html = StringIO()

            for tag in tags:
                html.write(TAG_LIST_ITEM % (tag['name'], tag['name']))

            return TAG_LIST_CONTAINER % html.getvalue()

        # we're not interesting in making HTML links out of the tags
        else:

            return str(', '.join([tag['name'] for tag in tags]))


def search(query, last_article_id=None):
    """Jesus"""

    # first we must assure query is valid...
    minimum_search_length = 3
    query_length = len(query)

    # query needs to be longer!
    if query_length < minimum_search_length:
        title = 'ERROR: Search query too short!'
        errors = LIST_TITLE % title
        errors += (
                   '<hr><p>Minimum query length is %d. The query <em>%s</em> '
                   'is %d characters long.</p>'
                   % (minimum_search_length, query, query_length)
                  )
        return errors, {'title': title, 'query': query}

    # now we can build information for query...
    last_article_id = last_article_id or '0'
    last_article_id = int(last_article_id)
    connection, cursor = connect()
    like_param = '%' + query + '%'

    # get every article ID which is a match for our query
    sql = '''
          SELECT article_id FROM article
          WHERE body LIKE ? OR title LIKE ?
          '''
    cursor.execute(sql, (like_param, like_param))
    results_article_ids = [row['article_id'] for row in cursor.fetchall()]
    results_total = len(results_article_ids)
    pages = int(math.ceil(float(results_total) / 5.0))

    # each element contains five article IDs--making "pages!"
    pages_of_ids = []

    # this allows us to jump to pages simply by specifying the minimum
    # article ID that should be present per page
    page_min_article_id = []

    for i in xrange(0, results_total, 5):
        ids = results_article_ids[i:i + 5]
        pages_of_ids.append(ids)
        page_min_article_id.append(min(ids))

    # if more than one page of results...
    if len(pages_of_ids) > 1:
        form = StringIO()
        form.write('<form action="/index.py" method="POST"" class="paginate">')
        form.write('<input type="hidden" name="search" value="%s">' % query)
        form.write('<ul class="links">')
        number_button = ('<li><button type="submit" value="%s" '
                         'name="last_article_id">%s</button></li>')

        for page_number, article_id in enumerate(page_min_article_id, start=1):

            if article_id == last_article_id:
                form.write('<li>%d</li>' % page_number)
            else:
                form.write(number_button % (article_id, page_number))

        form.write('</ul>')
        form.write('</form>')
        pagination = form.getvalue()

    else:
        pagination = None

    # get search result contents
    sql = '''
          SELECT article_id, title, body
          FROM article
          WHERE article_id >= ? AND body LIKE ? OR title LIKE ?
          ORDER BY article_id
          LIMIT 5
          '''
    params = (last_article_id, like_param, like_param)
    cursor.execute(sql, params)
    matches = cursor.fetchall()

    # build the HTML and output with substitutes
    html = StringIO()
    html_list, __ = doc.include('blog', 'entry_list.html')

    if matches:
        html.write(LIST_TITLE % query)
    else:
        title = 'ERROR: No results found for search/query.'
        html.write(LIST_TITLE % title)
        connection.close()
        html.write('<hr>' + NO_RESULTS % query)

        return html.getvalue(), {'title': title, 'query': query}

    if pagination:
        html.write(pagination)

    for match in matches:
        match['tags'] = get_tags_string(cursor, match['article_id'], True)
        html.write('<hr>\n' + doc.handlebars(html_list, match))

    connection.close()

    if pagination:
        html.write(pagination)

    subs = {
            'query': query,
            'title': query,
           }
    return html.getvalue(), subs


def article_save(article_id, title, tags, body, replicate=False):
    connection, cursor = connect()

    if replicate:
        cursor.execute('SELECT MAX(article_id) FROM article')
        article_id = cursor.fetchone()['MAX(article_id)'] + 1

    else:
        article_id = int(article_id)

    article_meta = {'title': title, 'body': body, 'replicate': replicate,
                    'tags': tags}
    article = Article(article_id, **article_meta)

    # return the article in edit mode...
    return article_load(article_id)


def article_load(article_id=None):
    """depr.?"""
    connection, cursor = connect()
    sql = 'SELECT * FROM article WHERE article_id=?'
    cursor.execute(sql, (article_id,))
    article_meta = cursor.fetchone()

    # build HTML
    js, __ = doc.include('blog', 'editor_js.html')
    html, __ = doc.include('blog', 'entry.html')
    content = js + html
    article_meta['tags'] = get_tags_string(cursor, article_id)
    content = doc.handlebars(content, article_meta)

    # build subs; return with content
    subs = {
            'permalink': PERMALINK % article_id,
           }
    subs.update(article_meta)

    return content, subs


def article_view(article_id=None):
    connection, cursor = connect()
    sql = 'SELECT * FROM article WHERE article_id=?'
    cursor.execute(sql, (article_id,))

    try:
        row = cursor.fetchone()
    except TypeError:
        connection.close()
        return None

    js, __ = doc.include('blog', 'editor_js.html')
    html, __ = doc.include('blog', 'entry.html')
    row['tags'] = get_tags_string(cursor, article_id)
    content = doc.handlebars(js + html, row)
    connection.close()
    subs = {
            'title': row['title'],
            'permalink': PERMALINK % row['article_id'],
           }
    subs.update(row)

    return content, subs


def article_list(tag=None):
    truncate_length = 225
    connection, cursor = connect()
    html_list, __ = doc.include('blog', 'entry_list.html')
    html = StringIO()

    if tag:
        sql = '''
              SELECT article_id, title, body FROM article_tag
              NATURAL JOIN tag
              NATURAL JOIN article
              WHERE tag.name=?
              '''
        cursor.execute(sql, (tag,))
        rows = cursor.fetchall()
        html.write(LIST_TITLE % tag)
        title = tag + ' @ ' + ARCHIVE_TITLEBAR

    else:
        cursor.execute('SELECT article_id, title, body FROM article')
        rows = cursor.fetchall()
        html.write(ARCHIVE_TITLE)
        title = ARCHIVE_TITLEBAR

    html.write('<hr>')

    if not rows:
        html.write(NO_ARTICLES_YET)

    for row in rows:
        row['tags'] = get_tags_string(cursor, row['article_id'], True)
        row['body'] = row['body'][:truncate_length]
        html.write(doc.handlebars(html_list, row))
        html.write('<hr>')

    connection.close()
    return (html.getvalue(), {'title': title})


def article_new():
    connection, cursor = connect()
    sql = 'SELECT MAX(article_id) FROM article'
    cursor.execute(sql)

    try:
        article_id = cursor.fetchone()['MAX(article_id)'] + 1

    # attempted to evaluate None + 1
    except TypeError:
        article_id = 1

    connection.close()
    subs = {
            'article_id': article_id,
            'title': 'title',
            'body': 'body',
            'tags': 'tags',
           }
    js, __ = doc.include('blog', 'editor_js.html')
    html, __ = doc.include('blog', 'entry.html')
    contents = doc.handlebars(js + html, subs)
    subs = {
            'title': 'new article',
            'permalink': PERMALINK % article_id,
           }

    return (contents, subs)


def editor(article_id):
    form = article_load(article_id)

    if form is None:
        form = article_new()

    return form

