from hier_config import HConfig
from hier_config.host import Host
import yaml

options = yaml.load(open('./tests/files/test_options_ios.yml'))
host = Host('brborder1', 'ios', options)

# Build HConfig object for the Running Config

running_config_hier = HConfig(host=host)
running_config_hier.load_from_file('./tests/files/brborder1_shrun.log')

# Build Hierarchical Configuration object for the Compiled Config

compiled_config_hier = HConfig(host=host)
compiled_config_hier.load_from_file('./tests/files/brborder1_add.log')

# Merge additional(compiled) config to running config

for child in compiled_config_hier.children:
#    print(child)
    if 'no ' in str(child):
        child_str = str(child)
        child_str = child_str.lstrip('no ')
#        print(child_str)
        running_config_hier.del_child_by_text(child_str)
    else:
        running_config_hier.add_deep_copy_del_of(child, merged=True)

for line in running_config_hier.all_children():
    print(line.cisco_style_text())
