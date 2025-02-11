from hier_config.base import HConfigBase

import re

__version__ = '1.6.0'


class HConfig(HConfigBase):

    """
    A class for representing and comparing Cisco configurations in a
    hierarchical tree data structure.

    Example usage:

    .. code:: python

        # Setup basic environment

        from hier_config import HConfig
        from hier_config.host import Host
        import yaml

        options = yaml.load(open('./tests/files/test_options_ios.yml'))
        host = Host('example.rtr', 'ios', options)

        # Build HConfig object for the Running Config

        running_config_hier = HConfig(host=host)
        running_config_hier.load_from_file('./tests/files/running_config.conf')

        # Build Hierarchical Configuration object for the Compiled Config

        compiled_config_hier = HConfig(host=host)
        compiled_config_hier.load_from_file('./tests/files/compiled_config.conf')

        # Build Hierarchical Configuration object for the Remediation Config

        remediation_config_hier = running_config_hier.config_to_get_to(compiled_config_hier)

        for line in remediation_config_hier.all_children():
            print(line.cisco_style_text())

    See:

        ./tests/files/test_tags_ios.yml and ./tests/files/test_options_ios.yml

        for test examples of options and tags.

    """

    def __init__(self, hostname=None, os=None, options=None, host=None):
        super(HConfig, self).__init__()
        if all([i is not None for i in (hostname, os, options)]):
            from hier_config.host import Host
            from warnings import warn
            self._host = Host(hostname, os, options)
            warning_message = """
            hostname, os, and options variables are being deprecated in version 2.0.0.
            Use the Host object going forward.
            Example:
                from hier_config.host import Host
                import yaml
                options = yaml.load(open('./tests/files/test_options_ios.yml'))
                host = Host({}, {}, options)
                hier = HConfig(host=host)""".format(hostname, os)
            warn(warning_message, SyntaxWarning)
        elif host is not None:
            assert hasattr(host, 'hostname')
            assert hasattr(host, 'os')
            assert hasattr(host, 'hconfig_options')
            self._host = host
        else:
            raise AttributeError('Error determining host object')

        self._options = self.host.hconfig_options
        self._logs = list()

    @property
    def host(self):
        return self._host

    @property
    def options(self):
        return self._options

    @property
    def logs(self):
        return self._logs

    @property
    def root(self):
        return self

    @property
    def is_leaf(self):
        return False

    @property
    def is_branch(self):
        return True

    @property
    def tags(self):
        t = set()
        for child in self.children:
            t.update(child.tags)
        return t

    @tags.setter
    def tags(self, value):
        for child in self.children:
            child.tags = value

    def __repr__(self):
        return 'HConfig(host={})'.format(self.host)

    def __str__(self):
        return repr(self)

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        if len(self.children) != len(other.children):
            return False

        for self_child, other_child in zip(sorted(self.children), sorted(other.children)):
            if self_child != other_child:
                return False
        return True

    def merge(self, other):
        """ Merges two HConfig objects """

        for child in other.children:
            self.add_deep_copy_of(child, merged=True)

    def load_from_file(self, file_path):
        """ Load configuration text from a file """

        with open(file_path) as f:
            config_text = f.read()
        self.load_from_string(config_text)

    def load_from_string(self, config_text):
        """ Create Hierarchical Configuration nested objects from text """

        for sub in self.options['full_text_sub']:
            config_text = re.sub(
                sub['search'],
                sub['replace'],
                config_text)

        current_section = self
        current_section.real_indent_level = -1
        most_recent_item = current_section
        indent_adjust = 0
        end_indent_adjust = []
        temp_banner = []
        in_banner = False
        banner_end_lines = ['EOF', '%', '!']
        banner_end_contains = []

        def end_of_banner_test(config_line):
            """
            :param config_line: type str
            :return: boolean
            """
            if config_line.startswith('^'):
                return True
            elif config_line in banner_end_lines:
                return True
            elif any([c in config_line for c in banner_end_contains]):
                return True
            return False

        for line in config_text.splitlines():
            # Process banners in configuration into one line
            if in_banner:
                if line != '!':
                    temp_banner.append(line)

                # Test if this line is the end of a banner
                if end_of_banner_test(str(line)):
                    in_banner = False
                    most_recent_item = self.add_child(
                        "\n".join(temp_banner), True)
                    most_recent_item.real_indent_level = 0
                    current_section = self
                    temp_banner = []
                continue
            else:
                # Test if this line is the start of a banner
                if line.startswith('banner '):
                    in_banner = True
                    temp_banner.append(line)
                    banner_words = line.split()
                    try:
                        banner_end_contains.append(banner_words[2])
                        banner_end_lines.append(banner_words[2][:1])
                        banner_end_lines.append(banner_words[2][:2])
                    except IndexError:
                        pass
                    continue

            actual_indent = len(line) - len(line.lstrip())
            line = ' ' * actual_indent + ' '.join(line.split())
            for sub in self.options['per_line_sub']:
                line = re.sub(
                    sub['search'],
                    sub['replace'],
                    line)
            line = line.rstrip()

            # If line is now empty, move to the next
            if not line:
                continue

            # Determine indentation level
            this_indent = len(line) - len(line.lstrip()) + indent_adjust

            line = line.lstrip()

            # Walks back up the tree
            while this_indent <= current_section.real_indent_level:
                current_section = current_section.parent

            # Walks down the tree by one step
            if this_indent > most_recent_item.real_indent_level:
                current_section = most_recent_item

            most_recent_item = current_section.add_child(line, True)
            most_recent_item.real_indent_level = this_indent

            for expression in self.options['indent_adjust']:
                if re.search(expression['start_expression'], line):
                    indent_adjust += 1
                    end_indent_adjust.append(expression['end_expression'])
                    break
            if end_indent_adjust and re.search(end_indent_adjust[0], line):
                indent_adjust -= 1
                del (end_indent_adjust[0])

        # Assert that we are not in a banner still for some reason
        assert not in_banner

#        if self.host.os in ['ios']:
#            self._remove_acl_remarks()
#            self._add_acl_sequence_numbers()
#            self._rm_ipv6_acl_sequence_numbers()

        return self

    def load_from_dump(self, dump):
        """
        Load a HConfig dump

        .. code:: python

            dump = [{
                'depth': child.depth(),
                'text': child.text,
                'tags': list(child.tags),
                'comments': list(child.comments),
                'new_in_config': child.new_in_config
            },]

        :param dump: list
        :return: None

        """
        from itertools import islice
        last_item = self
        for item in dump:
            # parent is the root
            if item['depth'] == 1:
                parent = self
            # has the same parent
            elif last_item.depth() == item['depth']:
                parent = last_item.parent
            # is a child object
            elif last_item.depth() + 1 == item['depth']:
                parent = last_item
            # has a parent somewhere closer to the root but not the root
            else:
                # last_item.lineage() = (a, b, c, d, e), new_item['depth'] = 2,
                # parent = a
                parent = next(islice(last_item.lineage(), item[
                              'depth'] - 2, item['depth'] - 1))
            # also accept 'line'
            # obj = parent.add_child(item.get('text', item['line']), force_duplicate=True)
            obj = parent.add_child(item['text'], force_duplicate=True)
            obj.tags = set(item['tags'])
            obj.comments = set(item['comments'])
            obj.new_in_config = item['new_in_config']
            last_item = obj

    def dump(self, lineage_rules=None):
        """
        Dump a list of loaded HConfig data

        .. code:: python

            dump = [{
                'depth': child.depth(),
                'text': child.text,
                'tags': list(child.tags),
                'comments': list(child.comments),
                'new_in_config': child.new_in_config
            },]

        :param lineage_rules: list
        :returns: list

        """

        if lineage_rules:
            children = self.all_children_sorted_with_lineage_rules(
                lineage_rules)
        else:
            children = self.all_children_sorted()

        output = []
        for child in children:
            output.append({
                'depth': child.depth(),
                'text': child.text,
                'tags': list(child.tags),
                'comments': list(child.comments),
                'new_in_config': child.new_in_config,
            })

        return output

    def add_tags(self, tag_rules, strip_negation=False):
        """
        Handler for tagging sections of Hierarchical Configuration data structure
        for inclusion and exclusion.
        """
        for rule in tag_rules:
            for child in self.all_children():
                if child.lineage_test(rule, strip_negation):
                    if 'add_tags' in rule:
                        child.append_tags(rule['add_tags'])
                    if 'remove_tags' in rule:
                        child.remove_tags(rule['remove_tags'])

        return self

    @staticmethod
    def depth():
        return 0

    def _add_acl_sequence_numbers(self):
        """
        Add ACL sequence numbers for use on configurations with a style of 'ios'

        """

        ipv4_acl_sw = 'ip access-list'
        # ipv6_acl_sw = ('ipv6 access-list')
        if self.host.os in ['ios']:
            acl_line_sw = ('permit', 'deny')
        else:
            acl_line_sw = ('permit', 'deny', 'remark')
        for child in self.children:
            if child.text.startswith(ipv4_acl_sw):
                sn = 10
                for sub_child in child.children:
                    if sub_child.text.startswith(acl_line_sw):
                        sub_child.text = "{} {}".format(sn, sub_child.text)
                        sn += 10

        return self

    def _rm_ipv6_acl_sequence_numbers(self):
        """
        If there are sequence numbers in the IPv6 ACL, remove them

        """

        for acl in self.get_children('startswith', 'ipv6 access-list '):
            for entry in acl.children:
                if entry.text.startswith('sequence'):
                    entry.text = ' '.join(entry.text.split()[2:])
        return self

    def _remove_acl_remarks(self):
        for acl in self.get_children('startswith', 'ip access-list '):
            for entry in acl.children:
                if entry.text.startswith('remark'):
                    acl.children.remove(entry)
        return self

    def all_children_sorted_with_lineage_rules(self, rules):
        """

        Args:

            rules: list of lineage rules

        Yields:

            instances of Hierarchical Configuration that match one of the lineage rules

        """

        yielded = set()
        matched = set()
        for child in self.all_children_sorted():
            for ancestor in child.lineage():
                if ancestor in matched:
                    yield child
                    yielded.add(child)
                    break
            else:
                for rule in rules:
                    if child.lineage_test(rule, False):
                        matched.add(child)
                        for ancestor in child.lineage():
                            if ancestor in yielded:
                                continue
                            yield ancestor
                            yielded.add(ancestor)
                        break

    def add_ancestor_copy_of(self, parent_to_add):
        """
        Add a copy of the ancestry of parent_to_add to self
        and return the deepest child which is equivalent to parent_to_add

        :param parent_to_add: type HConfig
        :return: base

        """

        base = self
        for parent in parent_to_add.lineage():
            if parent.root is not parent:
                base = base.add_shallow_copy_of(parent)

        return base

    def set_order_weight(self):
        """
        Sets self.order integer on all children

        """

        for child in self.all_children():
            for rule in self.options['ordering']:
                if child.lineage_test(rule):
                    child.order_weight = rule['order']

    def add_sectional_exiting(self):
        """
        Adds the sectional exiting text as a child

        """

        # TODO why do we need to delete the delete the sub_child and then
        # recreate it?
        for child in self.all_children():
            for rule in self.options['sectional_exiting']:
                if child.lineage_test(rule):
                    if rule['exit_text'] in child:
                        child.del_child_by_text(rule['exit_text'])

                    new_child = child.add_child(rule['exit_text'])
                    new_child.order_weight = 999
