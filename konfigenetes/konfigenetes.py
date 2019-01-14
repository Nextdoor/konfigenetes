import argparse
import pprint
import sys
from pathlib import Path

import yaml

parser = argparse.ArgumentParser(description='Konfigenetes configures Kubernetes resources dynamically.')
parser.add_argument('-f', '--input-file', dest='input_file_paths', action='append')
parser.add_argument('-r', '--add-resource', dest='resource_file_paths', action='append')
parser.add_argument('-p', '--add-patch', dest='patch_file_paths', action='append')
parser.add_argument('-s', '--set-var', dest='var_values', action='append')


def main():
    args = parser.parse_args()

    try:
        konfigured_resources = konfigenetes(
            args.input_file_paths,
            args.resource_file_paths,
            args.patch_file_paths,
            parse_var_values(args.var_values))
    except ValueError as e:
        print('Fatal Error:\n{}'.format(e))
        sys.exit(1)

    print(yaml.safe_dump_all(konfigured_resources, explicit_start=True))


def konfigenetes(input_file_paths=None, resource_file_paths=None,
                 patch_file_paths=None, var_values=None):
    if input_file_paths is None:
        input_file_paths = []

    if resource_file_paths is None:
        resource_file_paths = []

    if patch_file_paths is None:
        patch_file_paths = []

    if var_values is None:
        var_values = {}

    resource_file_paths_from_inputs = []
    patch_file_paths_from_inputs = []
    var_values_raw_from_inputs = []

    visited_input_files = set()
    new_input_files = input_file_paths

    while len(new_input_files) > 0:
        input_file_paths = new_input_files
        new_input_files = []

        for input_file_path in input_file_paths:
            if input_file_path in visited_input_files:
                # Prevent cycle.
                continue

            input_file_data = read_input_file(input_file_path)
            visited_input_files.add(input_file_path)

            new_input_files += input_file_data['input_file_paths']
            resource_file_paths_from_inputs += input_file_data['resource_file_paths']
            patch_file_paths_from_inputs += input_file_data['patch_file_paths']
            var_values_raw_from_inputs += input_file_data['var_values_raw']

    # Config passed into the function should take precedence (be applied after)
    # the config taken from input files.
    resource_file_paths = resource_file_paths_from_inputs + resource_file_paths
    patch_file_paths = patch_file_paths_from_inputs + patch_file_paths
    var_values_raw = var_values_raw_from_inputs

    resources = []
    for resource_file_path in resource_file_paths:
        with open(resource_file_path, 'r') as resource_file:
            resources += list(filter(
                lambda r: r is not None,
                yaml.safe_load_all(resource_file)))
    patches = []
    for patch_file_path in patch_file_paths:
        with open(patch_file_path, 'r') as patch_file:
            patches += list(filter(
                lambda p: p is not None,
                yaml.safe_load_all(patch_file)))

    # Add newly parsed var values to those passed in.
    # The order of dicts is important: New passed in vars must override the vars in the files.
    var_values = dict(
        parse_var_values(var_values_raw),
        **var_values)

    apply_patches(resources, patches)

    string_var_lists = None
    for resource in resources:
        string_var_lists = find_string_var_lists_recursive(resource, string_var_lists=string_var_lists)

    if string_var_lists is None:
        string_var_lists = []

    var_names = set([needed_var for string_var_list in string_var_lists
                     for needed_var in string_var_list.needed_vars])
    missing_vars = []
    for var_name in var_names:
        if var_name not in var_values:
            missing_vars.append(var_name)

    if missing_vars:
        missing_var_error = ''
        for missing_var in missing_vars:
            missing_var_error += '  Missing var: {{{{ {} }}}}\n'.format(missing_var)
        raise ValueError(missing_var_error)

    for string_var_list in string_var_lists:
        string_var_list.save(var_values)

    return resources


def parse_var_values(var_values_raw):
    var_values = {}
    for var_value_raw in var_values_raw:
        split_values = var_value_raw.split('=')
        if len(split_values) != 2:
            raise ValueError('Var must be in form of <VAR_NAME>=<VAR_VALUE>, was {}.'.format(var_value_raw))
        var_values[split_values[0]] = split_values[1]
    return var_values


def read_input_file(input_file_path):
    input_file_paths = []
    resource_file_paths = []
    patch_file_paths = []
    var_values_raw = []

    with open(input_file_path, 'r') as input_file:
        input_data = yaml.safe_load(input_file)
        if input_data is None:
            return

        if 'inputs' in input_data:
            if type(input_data['inputs']) != list:
                raise ValueError('"inputs" in input file {} must be a list.'.format(input_file_path))
            input_file_paths += [
                str(Path(input_file_path).parent / new_input_file_path)
                for new_input_file_path in input_data['inputs']]
        if 'resources' in input_data:
            if type(input_data['resources']) != list:
                raise ValueError('"resources" in input file {} must be a list.'.format(input_file_path))
            resource_file_paths += [
                str(Path(input_file_path).parent / resource_file_path)
                for resource_file_path in input_data['resources']]
        if 'patches' in input_data:
            if type(input_data['patches']) != list:
                raise ValueError('"patches" in input file {} must be a list.'.format(input_file_path))
            patch_file_paths += [
                str(Path(input_file_path).parent / patch_file_path)
                for patch_file_path in input_data['patches']]
        if 'vars' in input_data:
            if type(input_data['vars']) != list:
                raise ValueError('"vars" in input file {} must be a list.'.format(input_file_path))
            var_values_raw += input_data['vars']

    return {
        'input_file_paths': input_file_paths,
        'resource_file_paths': resource_file_paths,
        'patch_file_paths': patch_file_paths,
        'var_values_raw': var_values_raw,
    }


def apply_patches(resources, patches):
    for patch in patches:
        patch_name = patch.get('metadata', {}).get('name', None)
        patch_kind = patch.get('kind', None)
        if patch_name is None:
            raise ValueError('metadata.name must be set in all patches. Patch: {}'.format(pprint.pformat(patch)))
        if patch_kind is None:
            raise ValueError('kind must be set in all patches. Patch: {}'.format(pprint.pformat(patch)))
        for resource in resources:
            resource_name = resource.get('metadata', {}).get('name', None)
            resource_kind = resource.get('kind', None)
            if patch_name == resource_name and patch_kind == resource_kind:
                apply_patch_recursive(resource, patch)


def find_string_var_lists_recursive(resource, string_var_lists=None):
    if string_var_lists is None:
        string_var_lists = []

    for resource_key, resource_value in resource.items():
        if type(resource_value) == dict:
            find_string_var_lists_recursive(resource_value, string_var_lists=string_var_lists)
        elif type(resource_value) == list:
            for i in range(len(resource_value)):
                item = resource_value[i]
                if type(item) == dict:
                    find_string_var_lists_recursive(item, string_var_lists=string_var_lists)
                elif type(item) == str:
                    string_var_list = StringVarList(item, {
                        'list': resource_value,
                        'index': i,
                    })
                    if string_var_list.needs_vars():
                        string_var_lists.append(string_var_list)
        elif type(resource_value) == str:
            string_var_list = StringVarList(resource_value, {
                'dict': resource,
                'key': resource_key,
            })
            if string_var_list.needs_vars():
                string_var_lists.append(string_var_list)

    return string_var_lists


class StringVarList:
    def __init__(self, string, parent):
        self.string_parts = self.extract_parts(string)
        self.needed_vars = [value for var_type, value in self.string_parts
                            if var_type == 'var']
        self.parent = parent

    def needs_vars(self):
        return len(self.needed_vars) > 0

    def save(self, var_values):
        if 'list' in self.parent:
            self.parent['list'][self.parent['index']] = self.substitute_vars(var_values)
        elif 'dict' in self.parent:
            self.parent['dict'][self.parent['key']] = self.substitute_vars(var_values)

    def substitute_vars(self, var_values):
        substitution = []
        for var_type, value in self.string_parts:
            if var_type == 'text':
                substitution.append(value)
            elif var_type == 'var':
                substitution.append(var_values[value])
        return ''.join(substitution)

    def extract_parts(self, string):
        string_parts = []

        outer_left_curly = False
        inner_left_curly = False
        inner_right_curly = False

        text_string = ''
        var_string = ''

        for c in string:
            if not outer_left_curly:
                if c == '{':
                    outer_left_curly = True
                else:
                    text_string += c
            elif not inner_left_curly:
                if c == '{':
                    inner_left_curly = True
                    string_parts.append(('text', text_string))
                    text_string = ''
                else:
                    # Only one left curly, assume not a variable.
                    outer_left_curly = False
                    text_string += 'c'
            elif not inner_right_curly:
                if c == '}':
                    inner_right_curly = True
                    string_parts.append(('var', var_string.strip()))
                    var_string = ''
                else:
                    var_string += c
            else:
                if c == '}':
                    outer_left_curly = False
                    inner_left_curly = False
                    inner_right_curly = False
                else:
                    raise ValueError('Malformed var string: {}'.format(string))

        string_parts.append(('text', text_string))
        return string_parts


EXCLUDE_KEYS = {
    'apiVersion',
    'kind',
}


def apply_patch_recursive(resource, patch):
    for resource_key, resource_value in resource.items():
        if resource_key in EXCLUDE_KEYS:
            continue
        if resource_key in patch.keys():
            patch_value = patch[resource_key]
            if type(resource_value) != type(patch_value):
                raise ValueError(
                    'type mismatch between patch and resource: '
                    'resource["{}"] is {}, '
                    'patch["{}"] is {}'.format(resource_key, type(resource_value),
                                               resource_key, type(patch_value)))

            if type(resource_value) == dict:
                apply_patch_recursive(resource_value, patch_value)
            elif type(resource_value) == list:
                merge_lists(resource_value, patch_value)
            else:
                resource[resource_key] = patch_value

    for patch_key, patch_value in patch.items():
        if patch_key not in resource:
            resource[patch_key] = patch_value


def merge_lists(target_list, other_list):
    if len(target_list) == 0:
        target_list += other_list
    elif type(target_list[0]) == dict:
        merge_lists_of_dicts(target_list, other_list)
    else:
        target_list += other_list


def merge_lists_of_dicts(target_list, other_list):
    """
    Merge two lists of dicts.
    If an item has a name key in list one,
    it will be merged with an item with the same name key in the second list.
    """
    original_length = len(target_list)
    target_list += other_list

    named_items = {}
    # Iterate through first list and remember items with a name.
    for i in range(original_length):
        item = target_list[i]
        if 'name' in item:
            name = item['name']
            if name in named_items:
                named_items[name].append(i)
            else:
                named_items[name] = [i]

    # Iterate through the rest of the list and update named items.
    # If updated, remove the patched version from the list.
    i = original_length
    while i < len(target_list):
        item = target_list[i]
        if 'name' in item:
            name = item['name']
            if name in named_items:
                for item_index in named_items[name]:
                    for key in item.keys():
                        if key in target_list[item_index] and type(item[key]) == list:
                            merge_lists(target_list[item_index][key], item[key])
                        else:
                            target_list[item_index][key] = item[key]
                del target_list[i]
                # Don't increment i if we're splicing.
                continue
        i += 1


if __name__ == '__main__':
    main()
