# DistUpgradeFetcherCore.py 
#  
#  Copyright (c) 2006 Canonical
#  
#  Author: Michael Vogt <michael.vogt@ubuntu.com>
# 
#  This program is free software; you can redistribute it and/or 
#  modify it under the terms of the GNU General Public License as 
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
#  USA

from string import Template
import os
import apt_pkg
import apt
import tarfile
import socket
import urlparse
import urllib2
import tempfile
import shutil
import sys
import GnuPGInterface
from gettext import gettext as _
from aptsources.sourceslist import SourcesList

from utils import *

class DistUpgradeFetcherCore(object):
    " base class (without GUI) for the upgrade fetcher "

    DEFAULT_MIRROR="http://archive.ubuntu.com/ubuntu"
    DEFAULT_COMPONENT="main"
    DEBUG = "DEBUG_UPDATE_MANAGER" in os.environ

    def __init__(self, new_dist, progress):
        self.new_dist = new_dist
        self.current_dist_name = get_dist()
        self._progress = progress
        # options to pass to the release upgrader when it is run
        self.run_options = []

    def _debug(self, msg):
        " helper to show debug information "
        if self.DEBUG:
            sys.stderr.write(msg+"\n")

    def showReleaseNotes(self):
        return True

    def error(self, summary, message):
        """ dummy implementation for error display, should be overwriten
            by subclasses that want to more fancy method
        """
        print summary
        print message
        return False

    def authenticate(self):
        if self.new_dist.upgradeToolSig:
            f = self.tmpdir+"/"+os.path.basename(self.new_dist.upgradeTool)
            sig = self.tmpdir+"/"+os.path.basename(self.new_dist.upgradeToolSig)
            print "authenticate '%s' against '%s' " % (os.path.basename(f),os.path.basename(sig))
            if not self.gpgauthenticate(f, sig):
                return False

        # we may return False here by default if we want to make a sig
        # mandatory
        return True

    def gpgauthenticate(self, file, signature,
                        keyring='/etc/apt/trusted.gpg'):
        """ authenticated a file against a given signature, if no keyring
            is given use the apt default keyring
        """
        gpg = GnuPGInterface.GnuPG()
        gpg.options.extra_args = ['--no-options',
                                  '--homedir',self.tmpdir,
                                  '--no-default-keyring',
                                  '--ignore-time-conflict',
                                  '--keyring', keyring]
        proc = gpg.run(['--verify', signature, file],
                       create_fhs=['status','logger','stderr'])
        gpgres = proc.handles['status'].read()
        try:
            proc.wait()
        except IOError,e:
            # gnupg returned a problem (non-zero exit)
            print "exception from gpg: %s" % e
            print "Debug information: "
            print proc.handles['status'].read()
            print proc.handles['stderr'].read()
            print proc.handles['logger'].read()
            return False
        if "VALIDSIG" in gpgres:
            return True
        print "invalid result from gpg:"
        print gpgres
        return False

    def extractDistUpgrader(self):
          # extract the tarbal
          fname = os.path.join(self.tmpdir,os.path.basename(self.uri))
          print "extracting '%s'" % os.path.basename(fname)
          if not os.path.exists(fname):
              return False
          try:
              tar = tarfile.open(self.tmpdir+"/"+os.path.basename(self.uri),"r")
              for tarinfo in tar:
                  tar.extract(tarinfo)
              tar.close()
          except tarfile.ReadError, e:
              logging.error("failed to open tarfile (%s)" % e)
              return False
          return True

    def verifyDistUprader(self):
        # FIXME: check a internal dependency file to make sure
        #        that the script will run correctly
          
        # see if we have a script file that we can run
        self.script = script = "%s/%s" % (self.tmpdir, self.new_dist.name)
        if not os.path.exists(script):
            return self.error(_("Could not run the upgrade tool"),
                         _("Could not run the upgrade tool") + ".  " + _("This is most likely a bug in the upgrade tool. "
                          "Please report it as a bug"))
        return True

    def mirror_from_sources_list(self, uri, default_uri):
      """
      try to figure what the mirror is from current sources.list

      do this by looing for matching DEFAULT_COMPONENT, current dist
      in sources.list and then doing a http HEAD/ftp size request
      to see if the uri is available on this server
      """
      self._debug("mirror_from_sources_list: %s" % self.current_dist_name)
      sources = SourcesList(withMatcher=False)
      seen = set()
      for e in sources.list:
        if e.disabled or e.invalid or not e.type == "deb":
          continue
        # check if we probed this mirror already
        if e.uri in seen:
          continue
        # we are using the main mirror already, so we are fine
        if (e.uri.startswith(default_uri) and 
            e.dist == self.current_dist_name and
            self.DEFAULT_COMPONENT in e.comps):
          return uri
        elif (e.dist == self.current_dist_name and
              "main" in e.comps):
          mirror_uri = e.uri+uri[len(default_uri):]
          if url_downloadable(mirror_uri, self._debug):
            return mirror_uri
          seen.add(e.uri)
      self._debug("no mirror found")
      return ""

    def _expandUri(self, uri):
        """
        expand the uri so that it uses a mirror if the url starts
        with a well know string (like archive.ubuntu.com)
        """
        # try to guess the mirror from the sources.list
        if uri.startswith(self.DEFAULT_MIRROR):
          self._debug("trying to find suitable mirror")
          new_uri = self.mirror_from_sources_list(uri, self.DEFAULT_MIRROR)
          if new_uri:
            return new_uri
        # if that fails, use old method
        uri_template = Template(uri)
        m = country_mirror()
        new_uri = uri_template.safe_substitute(countrymirror=m)
        # be paranoid and check if the given uri is really downloadable
        try:
            if not url_downloadable(new_uri, self._debug):
              raise Exception("failed to download %s" % new_uri)
        except Exception,e:
            self._debug("url '%s' could not be downloaded" % e)
            # else fallback to main server
            new_uri = uri_template.safe_substitute(countrymirror='')
        return new_uri

    def fetchDistUpgrader(self):
        " download the tarball with the upgrade script "
        self.tmpdir = tmpdir = tempfile.mkdtemp()
        os.chdir(tmpdir)
        # turn debugging on here (if required)
        #apt_pkg.Config.Set("Debug::Acquire::http","1")
        fetcher = apt_pkg.GetAcquire(self._progress)
        if self.new_dist.upgradeToolSig != None:
            uri = self._expandUri(self.new_dist.upgradeToolSig)
            af = apt_pkg.GetPkgAcqFile(fetcher,uri, descr=_("Upgrade tool signature"))
        if self.new_dist.upgradeTool != None:
            self.uri = self._expandUri(self.new_dist.upgradeTool)
            af = apt_pkg.GetPkgAcqFile(fetcher,self.uri, descr=_("Upgrade tool"))
            if fetcher.Run() != fetcher.ResultContinue:
                return False
            # check that both files are really there and non-null
            for f in [os.path.basename(self.new_dist.upgradeToolSig),
                      os.path.basename(self.new_dist.upgradeTool)]:
                if not (os.path.exists(f) and os.path.getsize(f) > 0):
                    return False
            return True
        return False

    def runDistUpgrader(self):
        #print "runing: %s" % script
        args = [self.script]+self.run_options
        if os.getuid() != 0:
            os.execv("/usr/bin/sudo",["sudo"]+args)
        else:
            os.execv(self.script,args)

    def cleanup(self):
      # cleanup
      os.chdir("..")
      # del tmpdir
      shutil.rmtree(self.tmpdir)

    def run(self):
        # see if we have release notes
        if not self.showReleaseNotes():
            return
        if not self.fetchDistUpgrader():
            self.error(_("Failed to fetch"),
                  _("Fetching the upgrade failed. There may be a network "
                    "problem. "))
            return
        if not self.extractDistUpgrader():
            self.error(_("Failed to extract"),
                  _("Extracting the upgrade failed. There may be a problem "
                  "with the network or with the server. "))
                  
            return
        if not self.verifyDistUprader():
            self.error(_("Verfication failed"),
                  _("Verifying the upgrade failed.  There may be a problem "
                    "with the network or with the server. "))
            self.cleanup()
            return
        if not self.authenticate():
            self.error(_("Authentication failed"),
                  _("Authenticating the upgrade failed. There may be a problem "
                    "with the network or with the server. "))
            self.cleanup()
            return
        try:
          self.runDistUpgrader()
        except OSError, e:
          if e.errno == 13:
            self.error(_("Can not run the upgrade"),
                       _("This usually is caused by a system were /tmp "
                         "is mounted noexec. Please remount without "
                         "noexec and run the upgrade again."))
            return False
          else:
            self.error(_("Can not run the upgrade"),
                       _("The error message is '%s'." % e.strerror))
        return True

if __name__ == "__main__":
    d = DistUpgradeFetcherCore(None,None)
#    print d.authenticate('/tmp/Release','/tmp/Release.gpg')
    print "got mirror: '%s'" % d.mirror_from_sources_list("http://archive.ubuntu.com/ubuntu/dists/intrepid-proposed/main/dist-upgrader-all/0.93.34/intrepid.tar.gz", "http://archive.ubuntu.com/ubuntu")
