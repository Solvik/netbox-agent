import subprocess

class Dmidecode():
    def __init__(self):
        self.types = {
        0:  'bios',
        1:  'system',
        2:  'base board',
        3:  'chassis',
        4:  'processor',
        7:  'cache',
        8:  'port connector',
        9:  'system slot',
        10: 'on board device',
        11: 'OEM strings',
        #13: 'bios language',
        15: 'system event log',
        16: 'physical memory array',
        17: 'memory device',
        19: 'memory array mapped address',
        24: 'hardware security',
        25: 'system power controls',
        27: 'cooling device',
        32: 'system boot',
        41: 'onboard device',
        }
        self.content = self._get_output()
        self.info = self.parse_dmi()

    def parse_dmi(self):
        """
        Parse the whole dmidecode output.
        Returns a list of tuples of (type int, value dict).
        """
        self.info = []
        lines = iter(self.content.strip().splitlines())
        while True:
            try:
                line = next(lines)
            except StopIteration:
                break

            if line.startswith('Handle 0x'):
                typ = int(line.split(',', 2)[1].strip()[len('DMI type'):])
                if typ in self.types:
                    self.info.append(
                        (self.types[typ], self._parse_handle_section(lines))
                    )
        return self.info


    def _parse_handle_section(self, lines):
        """
        Parse a section of dmidecode output
        * 1st line contains address, type and size
        * 2nd line is title
        * line started with one tab is one option and its value
        * line started with two tabs is a member of list
        """
        data = {
            '_title': next(lines).rstrip(),
            }

        for line in lines:
            line = line.rstrip()
            if line.startswith('\t\t'):
                if isinstance(data[k], list):
                    data[k].append(line.lstrip())
            elif line.startswith('\t'):
                k, v = [i.strip() for i in line.lstrip().split(':', 1)]
                if v:
                    data[k] = v
                else:
                    data[k] = []
            else:
                break

        return data


    def _get_output(self):
        try:
            output = subprocess.check_output(
            'PATH=$PATH:/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin '
            'sudo dmidecode', shell=True)
        except Exception as e:
            print(e, file=sys.stderr)
            if str(e).find("command not found") == -1:
                print("please install dmidecode", file=sys.stderr)
                print("e.g. sudo apt install dmidecode",file=sys.stderr)

            sys.exit(1)
        return output.decode()

    def get(self, i):
        return [v for j, v in self.info if j == i]
