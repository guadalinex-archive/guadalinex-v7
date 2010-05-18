from ConfigParser import ConfigParser, NoOptionError


class DistUpgradeConfig(ConfigParser):
    def __init__(self):
        ConfigParser.__init__(self)
        self.read(['DistUpgrade.cfg'])
    def getlist(self, section, option):
        try:
            tmp = self.get(section, option)
        except NoOptionError:
            return []
        items = [x.strip() for x in tmp.split(",")]
        return items
    def getListFromFile(self, section, option):
        try:
            filename = self.get(section, option)
        except NoOptionError:
            return []
        items = [x.strip() for x in open(filename)]
        return filter(lambda s: not s.startswith("#") and not s == "", items)


if __name__ == "__main__":
    c = DistUpgradeConfig()
    print c.getlist("Distro","MetaPkgs")
    print c.getlist("Distro","ForcedPurges")
    print c.getListFromFile("Sources","ValidMirrors")
