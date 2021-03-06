"""
Convert cldoc XML to markdown
"""
import os
import glob
import argparse

from bs4 import BeautifulSoup
from jinja2 import Environment, DictLoader

# Jinja environment setup
api_template = """
{%for e in entries %}
{{ e }}
{% endfor %}
"""

class_template = """## **class** {{name}}
---
{{desc}}

{% if fields | length > 0%}
### Fields
| Name | Type | Description |
|:----:|:----:|:------------|
{%- for f in fields %}
| **{{f | field_info('name')}}** | `{{f | field_info('type')}}` | {{f | field_info('description')}} |
{%- endfor %}
{% endif %}

{% if variables | length > 0%}
### Variables
| Name | Type | Description |
|:----:|:----:|:------------|
{%- for f in variables %}
| **{{f | field_info('name')}}** | `{{f | field_info('type')}}` | {{f | field_info('description')}} |
{%- endfor %}
{% endif %}

{% if constructors | length > 0 %}
### Constructors
{% for c in constructors %}
#### {{c | func_info('name')}} ({{c | func_info('args_list') | join(', ')}})
> {{ c| func_info('description') }}
{% for a in c | func_info('args') %}
* **{{ a.name }}**    {{ a.description }}
{% endfor %}
{% endfor %}
{% endif %}

{% if destructors | length > 0 %}
### Destructors
{% for c in destructors %}
#### {{c | func_info('name')}} ({{c | func_info('args_list') | join(', ')}})
> {{ c| func_info('description') }}
{% for a in c | func_info('args') %}
* **{{ a.name }}**    {{ a.description }}
{% endfor %}
{% endfor %}
{% endif %}

{% if methods | length > 0 %}
### Methods
{% for c in methods %}
#### `{{c | func_info('return')}}` {{c | func_info('name')}} ({{c | func_info('args_list') | join(', ')}})
> {{ c| func_info('description') }}
{% for a in c | func_info('args') %}
* **{{ a.name }}**    {{ a.description }}
{% endfor %}
{% endfor %}
{% endif %}
"""

struct_template = """## **struct** {{name}}
---
{{desc}}

{% if fields | length > 0%}
### Fields
| Name | Type | Description |
|:----:|:----:|:------------|
{%- for f in fields %}
| **{{f | field_info('name')}}** | `{{f | field_info('type')}}` | {{f | field_info('description')}} |
{%- endfor %}
{% endif %}
"""

typedef_template = """
| Name | Type | Description |
|:----:|:----:|:------------|
{%- for td in typedefs %}
| **{{ td | field_info('name') }}** |  `{{ td | field_info('type')}}` | {{ td | field_info('description') }} |
{%- endfor %}
"""


def field_info(node, value):
    if value == 'name':
        return node.attrs['name']
    elif value == 'type':
        return node.find('type').attrs['name']
    elif value == 'description':
        return node.find('brief').text
    else:
        raise ValueError(f'Unrecognized option {value}')


def func_info(node, value):
    if value == 'name':
        return node.attrs['name']
    elif value == 'description':
        doc = node.find('doc')
        brief = node.find('brief')
        if doc is None:
            return brief.text if brief is not None else ''
        else:
            return doc.text
    elif value == 'args_list':
        args = node.findAll('argument')
        return [f'`{a.find("type").attrs["name"]}` {a.attrs["name"]}' for a in args]
    elif value == 'args':
        args = node.findAll('argument')
        return [{'name': a.attrs['name'],
                 'description': ''if a.find('doc') is None
                                else a.find('doc').text} for a in args]
    elif value == 'return':
        return node.find('return').find('type').attrs['name']
    else:
        raise ValueError(f'Unrecognized option {value}')


def parse_class(filename):
    # Parse the xml file
    with open(filename, 'r') as f:
        soup = BeautifulSoup(f, 'lxml')
    class_doc = soup.find('html').find('body').find('class')
    # Top level info
    name = class_doc.attrs['name']
    desc = class_doc.find('doc', recursive=False).text.replace('\n', ' ')
    # Parse Sections
    fields = class_doc.find_all('field', recursive=False)
    variables = class_doc.find_all('variable', recursive=False)
    constructors = class_doc.find_all('constructor', recursive=False)
    destructors = class_doc.find_all('destructor', recursive=False)
    methods = class_doc.find_all('method', recursive=False)
    # Render
    env = Environment(loader=DictLoader({'class': class_template}))
    env.filters.update({'field_info': field_info, 'func_info': func_info})
    return env.get_template('class').render(
        name=name,
        desc=desc,
        fields=fields,
        variables=variables,
        constructors=constructors,
        destructors=destructors,
        methods=methods
    )


def parse_struct(filename):
    with open(filename, 'r') as f:
        soup = BeautifulSoup(f, 'lxml')
    struct_doc = soup.find('html').find('body').find('struct')
    name = struct_doc.attrs['name']
    desc = struct_doc.find('brief', recursive=False).text.replace('\n', ' ')
    fields = struct_doc.find_all('field', recursive=False)
    env = Environment(loader=DictLoader({'struct': struct_template}))
    env.filters.update({'field_info': field_info})
    return env.get_template('struct').render(
        name=name, desc=desc, fields=fields,)


def parse_typedef(filename):
    with open(filename, 'r') as f:
        soup = BeautifulSoup(f, 'lxml')
    doc = soup.find('html').find('body').find('index')
    typedefs = doc.find_all('typedef', recursive=False)
    env = Environment(loader=DictLoader({'typedef': typedef_template}))
    env.filters.update({'field_info': field_info})
    return env.get_template('typedef').render(typedefs=typedefs,)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert XML from cldoc to Markdown')
    parser.add_argument('--xml_dir', help='Directory containing XML files generated by cldoc')
    parser.add_argument('--out_dir', help='Directory to print Markdown files to')
    args = parser.parse_args()
    # Get files and filetypes
    with open(os.path.join(args.xml_dir, 'index.xml'), 'r') as f:
        index = BeautifulSoup(f, 'lxml').find('html').find('body').find('index')
    entries = [(c.name, c.attrs['name']) for c in index if c.name is not None]
    entries = {k: [e[1] for e in entries if e[0] == k] for k in set([e[0] for e in entries])}
    # Setup environment
    env = Environment(loader=DictLoader({'api': api_template}))
    # Parse classes
    classes = []
    for c in entries['class']:
        classes.append(parse_class(os.path.join(args.xml_dir, f'{c}.xml')))
    with open(os.path.join(args.out_dir, 'classes.md'), 'w') as f:
        f.write(env.get_template('api').render(entries=classes))
    # Parse structs
    structs = []
    for c in entries['struct']:
        structs.append(parse_struct(os.path.join(args.xml_dir, f'{c}.xml')))
    with open(os.path.join(args.out_dir, 'structs.md'), 'w') as f:
        f.write(env.get_template('api').render(entries=structs))
    # Parse typedefs
    with open(os.path.join(args.out_dir, 'typedefs.md'), 'w') as f:
        f.write(parse_typedef(os.path.join(args.xml_dir, 'index.xml')))
