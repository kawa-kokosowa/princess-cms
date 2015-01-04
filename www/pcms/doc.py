"""note: should use snapshot from sakura?

"""

import cgi
import cgitb; cgitb.enable()
import os
from HTMLParser import HTMLParser
import re
import inspect


INCLUDE_DIRECTORY = 'include'
HEADER = 'Content-type:text/html\r\n\r\n'

EXPRESSION_INCLUDE = '''\[\[(.*?)\]\]'''
EXPRESSION_HANDLEBAR = '''{{(.*?)}}'''


class MLStripper(HTMLParser):
    """Thanks to StackOverflow...

    stackoverflow.com/questions/753052/strip-html-from-strings-in-python

    Removes HTML from string.

    """

    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def handlebars(s, d):
    """Returns formatted string, based on dictionary.

    I just had some qualms with the way the default formatter works.

    """

    for k,v in d.items():

        try:
            s = s.replace('{{' + k + '}}', v)
        except TypeError:
            s = s.replace('{{' + k + '}}', str(v))

    return s


def strip_html(html):
    """Return string without HTML!

    See: MLStripper!

    """

    s = MLStripper()
    s.feed(html)
    return s.get_data()


def include(*args, **kwargs):
    args = list(args)
    base = kwargs.get('base', False) or INCLUDE_DIRECTORY
    args.insert(0, base)
    path = os.path.join(*args)

    with open(path) as f:
        file_contents = f.read()

    return file_contents, path


# depr
def bracket_includes(s):
    """Return the inclusions found in s...

    [[path to file.html]]

    """

    # should do WHILE expression present
    for match in re.finditer(EXPRESSION_INCLUDE, s):
        replacement, __ = include(*match.group(1).split(' '))
        find = match.group()
        s = s.replace(find, replacement)

    return s


def evaluation_left(s):
    """Return true if there are file inclusions or handlebars present
    in the supplied parameter.

    Args:
      s (str): String to search for any file inclusions or
        handlebars.

    Returns:
      str|None: 'handlebar' if handlebars are present, 'include' if
        file inclusion is present, None if neither are present.

    Examples:
      >>> evaluation_left('asdf {{test}} blah blah')
      'handlebar'

      >>> evaluation_left('9afejspoaefsj [[inc somefile.txt]] {{test}}')
      'include'

      >>> evaluation_left('9jsfd0 {{test}} blah [[inc somefile.txt]]')
      'include'

      >>> evaluation_left('asdf9asdf asdfkjsdf0')
      None

    """

    if re.search(EXPRESSION_INCLUDE, s):
        return 'include'
    elif re.search(EXPRESSION_HANDLEBAR, s):
        return 'handlebar'
    else:
        return None


def evaluate(s, d=None):
    """Parse all handlebars and inclusions."""

    s_from_last_iter = None

    while True:
        whats_left = evaluation_left(s)

        if s_from_last_iter == s:
            break
        elif whats_left == 'include':  # always do includes first doy

            for match in re.finditer(EXPRESSION_INCLUDE, s):
                replacement, __ = include(*match.group(1).split(' '))
                find = match.group()
                s = s.replace(find, replacement)

        elif d and whats_left == 'handlebar':
            s = handlebars(s, d)
        else:
            break

        s_from_last_iter = s

    return s


class PyHTML(object):

    def __init__(self, page_string=None, page_path=None, head=None,
                 foot=None, subs=None, mapping=None):

        # either use a string or file contents for page (middle)
        if page_string:
            self.page = page_string
        else:
            self.page, self.page_path = include(*page_path)

        # include the head file contents...
        if not head:
            head = ['default', 'head.html']

        self.head, self.head_path = include(*head)

        # include the foot file contents...
        if not foot:
            foot = ['default', 'foot.html']

        self.foot, self.foot_path = include(*foot)

        # do replacements, form responses/mapping
        if mapping:
            subs = self.form(mapping)

        # do the [[include path.html]]
        self.head = evaluate(self.head, subs)
        self.page = evaluate(self.page, subs)
        self.foot = evaluate(self.foot, subs)


    def replace(self, subs, page=None):
        self.head = handlebars(self.head, subs)

        if page:
            page = handlebars(page, subs)
        else:
            self.page = handlebars(self.page, subs)

        self.foot = handlebars(self.foot, subs)

        if page:
            return page

    def __str__(self):
        return self.build()

    def build(self):
        return HEADER + self.head + self.page + self.foot

    def form(self, mapping):
        """Map HTML field names to (function, 

        Args:
          Just a dictionary with the following the field bool as a key,
          and the following dictionary as a value:

          function: Function to activate/evaluate
          args (list, optional): Field names whose values to use as
            arguments.
          kwargs (list, optional): same as above, but for specifying
            keyword arguments belonging to function.
          subs (dict, optional): find: replace dictionary for
            self.replace().
          head (str, optional): override the head file
          foot (str, optional): override the foot file

        """

        form = cgi.FieldStorage()
        new_page = ''

        for field_bool, command_dict in mapping.items(): 

            # field_bool must be present in POST/GET to proceed
            if not form.getvalue(field_bool):
                continue

            # the defined configuration for this function
            subs = command_dict.get('subs', None)
            function = command_dict['function']
            arg_names = command_dict.get('args', [])
            kwarg_names = command_dict.get('kwargs', [])

            # head, foot template file override
            if 'head' in command_dict:
                head_path = os.path.split(command_dict['head'])
                self.head, __ = include(*head_path)
                self.head = evaluate(self.head, subs)

            if 'foot' in command_dict:
                foot_path = os.path.split(command_dict['foot'])
                self.foot, __ = include(*foot_path)
                self.foot = evaluate(self.foot, subs)

            # has pre-defined parameters, so use them instead of detected
            if arg_names or kwarg_names:
                args = [form.getvalue(name) for name in arg_names]
                kwargs = {}

                for name in kwarg_names:
                    value = form.getvalue(name)

                    if value:
                        kwargs[name] = value

                function_eval = function(*args, **kwargs)

            # no pre-defined parameters!
            else:
                arg_spec = inspect.getargspec(function)

                # this function has parameters!
                if arg_spec:
                    # sorry, no varargs yet.
                    # we don't care about default kwarg values, either
                    args, __, keywords, __ = arg_spec

                    # now we fetch our (keyword) arguments from their
                    # respective fieldnames (POST/GET)
                    if args:
                        args = [form.getvalue(arg) for arg in args]
                    else:
                        args = []

                    if keywords:
                        kwargs = {form.getvalue(key) for key in keywords}
                    else:
                        kwargs = {}

                    function_eval = function(*args, **kwargs)

                # this function has no parameters!
                else:
                    function_eval = function()

            # PREPARE SUBSTITUTIONS!
            # Evaluated functions may return a string, OR a tuple of
            # (str, dict), dict being the substitutions.
            if type(function_eval) is type(tuple()):
                function_eval, function_eval_subs = function_eval

                # if substitutions were never defined before,
                # just use the new subs
                if subs is None:
                    subs = function_eval_subs

                # already have subs; update pre-existing subs
                else:
                    subs.update(function_eval_subs)

            # now we should be sure we have what should be the
            # intended output string of said function...
            new_page += function_eval

            # if substitutions were ever defined, do them now!
            if subs:
                new_page = evaluate(new_page, subs)

        # if a new page was generated at all, use it!
        if new_page:
            self.page = new_page

            if subs:
                self.head = evaluate(self.head, subs)
                self.page = evaluate(self.page, subs)
                self.foot = evaluate(self.foot, subs)

        if subs:
            return subs
        else:
            return None

