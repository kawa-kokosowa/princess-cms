#!/usr/local/bin/python
"""So far I have learned that it may be advantageous to utilize
a 'kwargs' entry in the typical mapping dictionary. Said entry
would be a dictionary.

"""


from francis import dec
from pcms.doc import PyHTML
from pcms.blog import editor
import sqlite3


mapping = {}
mapping['francis'] = {
                      'function': dec.i_stand_alone,
                      'subs': {'title': 'Francis E. Dec'},
                     }

# new article
mapping['new'] = {
                   'function': editor.article_new,
                   'subs': {'title': 'Blog Article...'},
                 }

# list articles; if tag is specified, filter by tag
mapping['list'] = {
                    'function': editor.article_list,
                    'args': ['tag'],
                    'head': 'blog/head/list.html',
                    'foot': 'blog/foot-list.html',
                  }

# view an article
mapping['view'] = {
                   'function': editor.article_view,
                   'args': ['view'],
                   'subs': {'title': 'Blog Article...'},
                  }

# save article
mapping['save'] = {
                   'function': editor.article_save,
                   'args': ['article_id', 'title', 'tags', 'body'],
                   'subs': {'title': 'Blog Post'},
                  }

# create a new user
mapping['new_user'] = {
                       'function': editor.user_new,
                       'args': ['username', 'password', 'email', 'comment'],
                       'subs': {'title': 'Blog Article...'},
                      }

# user login
mapping['login'] = {
                    'function': editor.user_login,
                    'kwargs': ['username', 'password'], 
                    'subs': {'title': 'Account Login'},
                   }

# clone/replace an article
mapping['replicate'] = {
                        'function': editor.article_save,
                        'args': ['article_id', 'title', 'tags', 'body',
                                 'replicate'],
                        'subs': {'title': 'Blog Post'},
                       }

# search through articles
# the list tag filter belongs here, truly.
mapping['search'] = {
                     'function': editor.search,
                     'args': ['search', 'last_article_id'],
                     'subs': {'title': 'search'},
                     'head': 'blog/head/search.html',  # these should really be lists being pased for os.path.join...
                     'foot': 'blog/foot-list.html',
                    }

# delete an article
mapping['delete'] = {'function': editor.delete}

# danger mode reset button
mapping['install'] = {'function': editor.install}

# build and "print" page
subs = {'title': 'this is a title!'}
default_page = 'Check install...'
head = ['blog', 'head', 'default.html']
foot = ['blog', 'foot.html']
print PyHTML(default_page, subs=subs, mapping=mapping, head=head, foot=foot)
# you can use page as a default form

