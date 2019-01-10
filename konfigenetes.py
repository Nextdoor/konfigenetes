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
            args.var_values)
    except ValueError as e:
        print(f'Fatal Error:\n{e}')
        sys.exit(1)

    print(yaml.dump_all(konfigured_resources, explicit_start=True))


def konfigenetes(input_file_paths=None, resource_file_paths=None,
                 patch_file_paths=None, var_values_raw=None):
    if input_file_paths is None:
        input_file_paths = []

    if resource_file_paths is None:
        resource_file_paths = []

    if patch_file_paths is None:
        patch_file_paths = []

    if var_values_raw is None:
        var_values_raw = []

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
    var_values_raw = var_values_raw_from_inputs + var_values_raw

    resources = []
    for resource_file_path in resource_file_paths:
        with open(resource_file_path, 'r') as resource_file:
            resources += list(filter(
                lambda r: r is not None,
                yaml.load_all(resource_file)))
    patches = []
    for patch_file_path in patch_file_paths:
        with open(patch_file_path, 'r') as patch_file:
            patches += list(filter(
                lambda p: p is not None,
                yaml.load_all(patch_file)))

    var_values = {}
    for var_value_raw in var_values_raw:
        split_values = var_value_raw.split('=')
        if len(split_values) != 2:
            raise ValueError(f'Var must be in form of <VAR_NAME>=<VAR_VALUE>, was {var_value_raw}.')
        var_values[split_values[0]] = split_values[1]

    apply_patches(resources, patches)

    needed_vars = None
    for resource in resources:
        needed_vars = find_vars_recursive(resource, needed_vars=needed_vars)

    if needed_vars is None:
        needed_vars = []

    var_names = set([needed_var['var'] for needed_var in needed_vars])
    missing_vars = []
    for var_name in var_names:
        if var_name not in var_values:
            missing_vars.append(var_name)

    if missing_vars:
        missing_var_error = ''
        for missing_var in missing_vars:
            missing_var_error += f'  Missing var: {{{{ {missing_var} }}}}\n'
        raise ValueError(missing_var_error)

    for needed_var in needed_vars:
        if 'list' in needed_var:
            needed_var['list'][needed_var['index']] = var_values[needed_var['var']]
        elif 'dict' in needed_var:
            needed_var['dict'][needed_var['key']] = var_values[needed_var['var']]

    return resources


def read_input_file(input_file_path):
    input_file_paths = []
    resource_file_paths = []
    patch_file_paths = []
    var_values_raw = []

    with open(input_file_path, 'r') as input_file:
        input_data = yaml.load(input_file)
        if input_data is None:
            return

        if 'inputs' in input_data:
            if type(input_data['inputs']) != list:
                raise ValueError(f'"inputs" in input file {input_file_path} must be a list.')
            input_file_paths += [
                Path(input_file_path).parent / new_input_file_path
                for new_input_file_path in input_data['inputs']]
        if 'resources' in input_data:
            if type(input_data['resources']) != list:
                raise ValueError(f'"resources" in input file {input_file_path} must be a list.')
            resource_file_paths += [
                Path(input_file_path).parent / resource_file_path
                for resource_file_path in input_data['resources']]
        if 'patches' in input_data:
            if type(input_data['patches']) != list:
                raise ValueError(f'"patches" in input file {input_file_path} must be a list.')
            patch_file_paths += [
                Path(input_file_path).parent / patch_file_path
                for patch_file_path in input_data['patches']]
        if 'vars' in input_data:
            if type(input_data['vars']) != list:
                raise ValueError(f'"vars" in input file {input_file_path} must be a list.')
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
            raise ValueError(f'metadata.name must be set in all patches. Patch: {pprint.pformat(patch)}')
        if patch_kind is None:
            raise ValueError(f'kind must be set in all patches. Patch: {pprint.pformat(patch)}')
        for resource in resources:
            resource_name = resource.get('metadata', {}).get('name', None)
            resource_kind = resource.get('kind', None)
            if patch_name == resource_name and patch_kind == resource_kind:
                apply_patch_recursive(resource, patch)


def find_vars_recursive(resource, needed_vars=None):
    if needed_vars is None:
        needed_vars = []

    for resource_key, resource_value in resource.items():
        if type(resource_value) == dict:
            find_vars_recursive(resource_value, needed_vars=needed_vars)
        elif type(resource_value) == list:
            for i in range(len(resource_value)):
                item = resource_value[i]
                if type(item) == dict:
                    find_vars_recursive(item, needed_vars=needed_vars)
                elif type(item) == str:
                    var_name = var_name_for_string(item)
                    if var_name is not None:
                        needed_vars.append({
                            'list': resource_value,
                            'index': i,
                            'var': var_name,
                        })
        elif type(resource_value) == str:
            var_name = var_name_for_string(resource_value)
            if var_name is not None:
                needed_vars.append({
                    'dict': resource,
                    'key': resource_key,
                    'var': var_name,
                })

    return needed_vars


def var_name_for_string(input_string):
    if input_string.startswith('{{') and input_string.endswith('}}'):
        return input_string[2:-2].strip()
    return None


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
                    f'resource["{resource_key}"] is {type(resource_value)}, '
                    f'patch["{resource_key}"] is {type(patch_value)}')

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
    target_list += other_list

    named_items = {}
    # Iterate through first list and remember items with a name.
    for i in range(0, len(other_list)):
        item = target_list[i]
        if 'name' in item:
            name = item['name']
            if name in named_items:
                named_items[name].append(i)
            else:
                named_items[name] = [i]

    # Iterate through the rest of the list and update named items.
    # If updated, remove the patched version from the list.
    i = len(other_list)
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
