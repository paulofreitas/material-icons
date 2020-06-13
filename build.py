#!/usr/bin/env python3
# Before using, install dependencies: pip install fonttools lxml pybars3
from fontTools import ttx
from lxml import etree
from pybars import Compiler
from urllib.parse import quote_plus, urlparse, urlencode
from urllib.request import urlopen
import datetime
import json
import os
import re
import yaml

def fix_ligature_name(name):
    replace = {
        'underscore': '_',
        'digit_': '',
        'zero': '0',
        'one': '1',
        'two': '2',
        'three': '3',
        'four': '4',
        'five': '5',
        'six': '6',
        'seven': '7',
        'eight': '8',
        'nine': '9',
    }

    for old, new in replace.items():
        name = ','.join(component.replace(old, new) for component in name.split(','))

    return name.replace(',', '')

def convert_glyph_unicode(glyph):
    if re.match('uni[0-9A-F]{4}', glyph):
        return (b'\\u' + bytes(glyph[3:], 'utf-8')).decode('unicode_escape')

    if re.match('u[0-9A-F]{4,6}', glyph):
        return (b'\\u' + bytes(glyph[1:], 'utf-8')).decode('unicode_escape')

    return glyph

def get_font_file(font_family):
    iconfont_css = str(urlopen('https://fonts.googleapis.com/icon?' \
        + urlencode(dict(family=font_family))).read())

    return re.findall('https?://[^)]+', iconfont_css)[-1]

def length_helper(this, *args, **kwargs):
    if not args:
        return None

    return len(args[0])

def quote_helper(this, *args, **kwargs):
    return quote_plus(*args, **kwargs)

def timestamp_helper(this, *args, **kwargs):
    now = datetime.datetime.now()

    if kwargs.get('format') == 'isoformat':
        return now.isoformat(sep=' ', timespec='seconds')

    return int(now.timestamp())

if __name__ == '__main__':
    THEMES = yaml.safe_load(open('data/themes.yaml'))

    print('Getting icon fonts...')

    font_files = {}

    try:
        os.mkdir('build')
    except FileExistsError:
        pass

    os.chdir('build/')

    for theme in THEMES:
        external_font_file = get_font_file(theme['font_family'])
        local_font_file = theme['name'] + os.path.splitext(urlparse(external_font_file).path)[1]
        font_files[theme['name']] = local_font_file
        open(local_font_file, 'wb').write(urlopen(external_font_file).read())

    print('Extracting font glyphs...')

    icons = {}
    theme_icons_mapping = {}

    for theme in THEMES:
        ttx.process(*ttx.parseOptions(['-f', '-t', 'GSUB', font_files[theme['name']]]))

        tree = etree.parse('{}.ttx'.format(theme['name']))
        theme_icons = []

        for ligature_set in tree.findall('/GSUB/LookupList/Lookup/LigatureSubst/LigatureSet'):
            for ligature in ligature_set.findall('Ligature'):
                icon_name = fix_ligature_name(ligature_set.attrib['glyph']) \
                    + fix_ligature_name(ligature.attrib['components'])
                icon_codepoint = convert_glyph_unicode(ligature.attrib['glyph'])

                if icon_name not in icons:
                    icons[icon_name] = icon_codepoint

                theme_icons.append(icon_name)

        theme_icons_mapping[theme['name']] = sorted(theme_icons)

    print('Publishing files...')

    for theme in THEMES:
        theme['codepoints'] = {}
        theme['icons'] = []

        for icon_name in theme_icons_mapping[theme['name']]:
            theme['codepoints'][icon_name] = icons[icon_name]
            theme['icons'].append(dict(
                name=icon_name,
                codepoint='\\' + bytes(icons[icon_name], 'unicode_escape').decode('utf-8')[2:] \
                    if icons[icon_name] != icon_name else icon_name))

    hbs = Compiler()
    template = hbs.compile(open('../data/template.hbs').read())
    template_helpers = {'length': length_helper,
                        'quote': quote_helper,
                        'timestamp': timestamp_helper}
    os.chdir('../docs/')

    for theme in THEMES:
        theme['active'] = True
        template_data = dict(themes=THEMES, theme=theme)

        if theme['name'] != 'baseline':
            try:
                os.mkdir(theme['name'])
            except FileExistsError:
                pass

            os.chdir(theme['name'])

        json.dump(theme['codepoints'], open('codepoints.json', 'w'), indent=4)
        open('index.html', 'w').write(template(template_data, helpers=template_helpers))

        del theme['active']

        if theme['name'] != 'baseline':
            os.chdir('..')