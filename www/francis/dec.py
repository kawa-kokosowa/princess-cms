import ConfigParser
import sqlite3 as sqlite

# example function
# should have random chance to capitalize!
def load_words():
    words = {}

    with open('francis/words.ini') as f:
        ini = ConfigParser.ConfigParser()
        ini.readfp(f)

        for k,v in ini._sections.items():

            if v.get('var'):
                del v['var']

            if v['__name__']:
                del v['__name__']

            words[k] = v

    return words


def i_stand_alone():
    words = load_words()
    connection = sqlite.connect(':memory:')
    cursor = connection.cursor()
    sql = '''
          CREATE TABLE words
          (
           word PRIMARY KEY,
           type TEXT NOT NULL,
           friendly TEXT,
           target TEXT
          )
          '''
    cursor.execute(sql)

    for word, attributes in words.items():
        word_type = attributes.get('type', None)
        friendly = attributes.get('friendly', None)
        target = attributes.get('target', None)
        sql = '''
              INSERT INTO words (word, type, friendly, target)
              VALUES (?, ?, ?, ?)
              '''
        cursor.execute(sql, (word, word_type, friendly, target))

    connection.commit()
    seen_words = []

    def get_word(**kwargs):
        import random

        sql = 'SELECT word FROM words WHERE '
        fields = [f for f in kwargs]
        suffix = ' AND '.join(['%s=?' % f for f in kwargs])
        sql += suffix + ' ORDER BY RANDOM() LIMIT 1'
        cursor.execute(sql, kwargs.values())
        word = cursor.fetchone()[0]

        if word in seen_words:
            cursor.execute(sql, kwargs.values())
            word = cursor.fetchone()[0]

        seen_words.append(word)
        string = word
        no_dubs = ('verbage', 'noun', 'epilog', 'afflicting', 'prolog')

        if random.randint(0, 1) and kwargs.get('type', None) not in no_dubs:
            cursor.execute(sql, kwargs.values())
            new_word = cursor.fetchone()[0]

            # to avoid stuff like computer god-computer god
            if (new_word != word and new_word not in word
                and word not in new_word):

                string += "-" + new_word
                seen_words.append(new_word)

        if random.randint(1, 100) > 70:
            string = string.upper()

        if random.randint(0, 1):
            string = string.replace('THE', 'YOUR')

        return string

    # plural_noun_target_victimi, antagonist, antagonist_adjective,
    # antagonist_device, antagonist_device_adjective,
    subs = {}
    subs['prolog'] = get_word(type='prolog')
    subs['victim'] = get_word(type='noun', friendly='yes')
    subs['antagonist'] = get_word(friendly='no', target='antagonist',
                                  type='noun')
    subs['antagonist-verb'] = get_word(type='verbage', friendly='no')
    subs['antagonist-afflicting'] = get_word(type='afflicting', friendly='no')
    subs['antagonist-afflicting-adj'] = get_word(type='adjective',
                                                 friendly='no')
    subs['antagonist-adj'] = get_word(friendly='no', type='adjective')
    subs['antagonist-dev'] = get_word(target='device', type='noun')
    subs['antagonist-alt'] = get_word(target='device', type='noun')
    subs['antagonist-alt2'] = get_word(target='device', type='noun')
    subs['antagonist-dev-adj'] = get_word(target='device', type='adjective')
    subs['antagonist-xtra-adj'] = get_word(type='adjective', friendly='no')
    subs['epilog'] = get_word(type='epilog')
    subs['closing'] = get_word(type='closing')

    # form the madlib and return!
    madlib = (
              "%(prolog)s %(antagonist-adj)s "
              "%(antagonist-xtra-adj)s %(antagonist)s %(antagonist-verb)s "
              "%(antagonist-dev-adj)s %(antagonist-dev)s "
              "%(antagonist-afflicting-adj)s %(antagonist-alt)s "
              "%(antagonist-alt2)s %(antagonist-afflicting)s %(victim)s "
              "%(epilog)s<br><br>%(closing)s"
              % subs
             ) 
    connection.close()

    return madlib

